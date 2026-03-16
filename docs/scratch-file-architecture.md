# Scratch File Architecture

## Context

BeeRef currently keeps all image data in memory and writes to the .bee file only on explicit Save. This means: (1) crash = lose everything since last save, (2) Save-As with unloaded placeholders can't work without all blobs in memory, (3) no autosave.

This design introduces a scratch file (working copy) pattern — the same approach Photoshop uses with its scratch disk. The working copy is always reasonably current, Save is cheap, and crash recovery is free.

## File naming

```
file.bee          — the user's file (untouched until Save)
file.bee.swp      — working copy (always current, unhidden)
```

The `.swp` extension is unhidden because: works the same on all platforms (no Windows hidden attribute dance), universally recognizable as a temp file, easier to find for manual recovery.

The `.swp` file's presence on disk is the crash-recovery signal — on clean exit it's always deleted.

## How it works

### Open

1. Read metadata from original .bee file (read-only, fast — items table only, no blobs)
2. Show placeholders, `fit_scene()`
3. Background: copy original .bee → `file.bee.swp`
4. Background: VACUUM the working copy (compacts free pages, runs while user is orienting)
5. When copy finishes: start `ImageLoader` against the working copy

The user sees the layout instantly. The copy overlaps with the user looking at placeholders. By the time they scroll, the copy + VACUUM are likely done and images start loading.

### During operation

Scene is in-memory as today. Changes accumulate in the undo stack. Periodically (timer, e.g., every 60s if dirty, or on idle), drain changes to the working copy:

- **Drain** = iterate scene items, write metadata updates to the working copy's `items` table (same diff logic as current `write_data`)
- **New images** (paste, drag-in) get their blob written to the working copy's `sqlar` immediately on insert — they get a `save_id` right away
- **Deleted items** are removed from the working copy during drain
- **Drain is cheap** — metadata rows are small, blobs are only written for genuinely new images
- **No VACUUM during drain** — unnecessary overhead for an intermediate state

### Save

1. Final drain (flush any pending changes to working copy)
2. Copy working copy → temp file in the same directory (`tempfile.NamedTemporaryFile(dir=..., delete=False)`)
3. `os.replace(temp_file, file.bee)` — atomic swap of the original
4. Working copy stays intact, we keep operating against it

The working copy is never moved or invalidated. The original gets atomically replaced by a clean snapshot. The temp file gets a random name (e.g., `tmpx7k2f9.bee`), so no naming collisions. If the copy in step 2 fails or we crash mid-copy, the original is untouched, the working copy is still valid, and the orphaned temp file is harmless.

```python
with tempfile.NamedTemporaryFile(
    dir=os.path.dirname(bee_path), suffix='.bee', delete=False
) as tmp:
    shutil.copy2(working_copy, tmp.name)
os.replace(tmp.name, bee_path)  # atomic (same filesystem)
```

### Save-As

1. Final drain
2. Copy working copy → new path
3. Continue operating against the working copy (or switch to a new working copy of the new file)

Works with placeholders — blobs are in the working copy's sqlar, not in memory.

### Crash recovery

On open, check for `file.bee.swp`. If it exists:
- The previous session crashed (or was killed)
- Offer to recover: "Found unsaved changes from a previous session. Recover?"
- Yes → open the working copy as the source instead of the original
- No → delete the working copy, open the original normally

### Close / New Scene

1. Final drain (if user chose to save)
2. Delete the working copy (`file.bee.swp`)
3. Clean up ImageLoader and SQLite connections

On clean exit, no `.swp` file remains.

## Interaction with async loading

The scratch file is the single source for blob reads:

```
Original .bee                Working copy (.bee.swp)
  (read-only)                  (read-write)
      |                              |
  read metadata              copy from original (bg)
      |                       VACUUM (bg)
  show placeholders                  |
      |                       ImageLoader reads blobs
      |                       drains write metadata
      |                       new image blobs written
      |                              |
  Save: ---copy to tmpfile, rename-->  original
```

The `ImageLoader` always reads from the working copy. Drains write to the working copy. No contention with the original file after the initial copy.

## SQLite concurrency

The working copy is accessed by:
- `ImageLoader` thread: reads blobs from `sqlar`
- Drain (main thread or dedicated thread): writes metadata to `items`, writes new blobs to `sqlar`

SQLite in WAL mode handles this cleanly — concurrent readers + one writer. Without WAL, we'd need to serialize blob reads and drain writes, but they're unlikely to overlap in practice (drain is fast).

## Disk cost

Temporary 2x file size during operation (original + working copy), plus a brief 3x during Save (original + working copy + temp file). For a 500MB .bee file that's 500MB–1GB extra. Photoshop users routinely eat 10x+ scratch disk costs; this is modest by comparison. The working copy is deleted on clean exit, and the .saving file is transient.

## Future: mip storage

With the scratch file in place, storing pre-computed mips in the working copy becomes natural:
- On first load of an image, write mip blobs to a `mips` table in the working copy
- Subsequent opens can use cached mips from the working copy (if recovering) or regenerate
- Save could optionally include mips in the final .bee file for faster future opens

## Implementation order

This is a follow-up to the basic placeholder/async loading. The sequence:

1. **First**: Placeholder + async loading (current plan in `async-image-loading.md`)
   - ImageLoader reads from original file (read-only)
   - Save/Save-As deferred (force-load-all as stopgap)
2. **Second**: Scratch file
   - ImageLoader reads from working copy
   - Drain replaces explicit save logic
   - Save = drain + copy + atomic rename
   - Save-As = drain + copy
   - Crash recovery
3. **Third**: Autosave timer + mip caching
