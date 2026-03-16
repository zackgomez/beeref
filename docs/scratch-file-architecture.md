# Scratch File Architecture

## Context

BeeRef currently keeps all image data in memory and writes to the .bee file only on explicit Save. This means: (1) crash = lose everything since last save, (2) Save-As with unloaded placeholders can't work without all blobs in memory, (3) no autosave.

This design introduces a scratch file (working copy) pattern — the same approach Photoshop uses with its scratch disk. The working copy is always reasonably current, Save is cheap, and crash recovery is free.

## Recovery directory

All working copies live in a central recovery directory, not next to the original file:

```
~/.config/BeeRef/recovery/          (Linux)
%APPDATA%/BeeRef/recovery/          (Windows)
~/Library/Application Support/BeeRef/recovery/  (macOS)
```

BeeSettings already knows the config dir — we just add `recovery/` underneath.

### Working copy naming

Each .swp is named deterministically from the original path to avoid collisions:

```python
# /home/zack/Mythos Sync/tributes.bee → recovery/tributes_a1b2c3d4.bee.swp
stem = Path(original).stem
path_hash = hashlib.sha256(str(original).encode()).hexdigest()[:8]
swp_name = f"{stem}_{path_hash}.bee.swp"
```

For new (unsaved) scenes: `untitled_{timestamp}.bee.swp`

### Benefits over .swp-next-to-file

- Works on read-only filesystems, network drives, removable media
- No stray files appearing next to user's documents
- Recovery dir is a single place to scan on startup
- No filesystem permission issues

## How it works

### Open existing file

1. Read metadata from original .bee file (read-only, fast — items table only, no blobs)
2. Show placeholders, `fit_scene()`
3. Background: copy original .bee → .swp in recovery dir
4. Background: VACUUM the working copy (compacts free pages, runs while user is orienting)
5. When copy finishes: start `ImageLoader` against the working copy

The user sees the layout instantly. The copy overlaps with the user looking at placeholders.

### New scene (no file)

1. Create empty .swp in recovery dir (`untitled_{timestamp}.bee.swp`)
2. No copy needed — .swp starts empty
3. New images written to .swp immediately (get a `save_id` right away)
4. First Save triggers a Save-As dialog to pick a path

The .swp is the only file until the user saves.

### Read-only file

Same as normal open — the original is never written to anyway. The .swp is in the recovery dir which is always user-writable. Save is disabled (original path is read-only), Save-As works.

### During operation

Scene is in-memory as today. Changes accumulate in the undo stack. Periodically (timer, e.g., every 60s if dirty, or on idle), drain changes to the working copy:

- **Drain** = iterate scene items, write metadata updates to the working copy's `items` table (same diff logic as current `write_data`)
- **New images** (paste, drag-in) get their blob written to the working copy's `sqlar` immediately on insert — they get a `save_id` right away
- **Deleted items** are removed from the working copy during drain
- **Drain is cheap** — metadata rows are small, blobs are only written for genuinely new images
- **No VACUUM during drain** — unnecessary overhead for an intermediate state

### Save

```
Save pressed:
  if no original path → Save-As dialog (user picks path)
  elif original is read-only → "File is read-only. Use Save-As."
  else → drain + copy + atomic rename (below)
```

1. Final drain (flush pending changes to working copy)
2. Copy working copy → temp file in the same directory as original (`tempfile.NamedTemporaryFile(dir=..., delete=False)`)
3. `os.replace(temp_file, original)` — atomic swap
4. Working copy stays intact, we keep operating against it

```python
with tempfile.NamedTemporaryFile(
    dir=os.path.dirname(bee_path), suffix='.bee', delete=False
) as tmp:
    shutil.copy2(working_copy, tmp.name)
os.replace(tmp.name, bee_path)  # atomic (same filesystem)
```

The working copy is never moved or invalidated. If the copy fails or we crash mid-copy, the original is untouched and the working copy is still valid.

### Save-As

1. Final drain
2. Copy working copy → new path
3. Rename .swp in recovery dir to match the new path:
   - Close SQLite connection
   - `os.rename(old_swp, derive_swp_name(new_path))`
   - Reopen connection against new .swp path
4. Continue operating against the renamed working copy

Same rename happens when an untitled scene does its first Save — the `untitled_{timestamp}.bee.swp` becomes `{filename}_{hash}.bee.swp`.

Works with placeholders — blobs are in the working copy's sqlar, not in memory.

### Close / New Scene

1. Final drain (if user chose to save)
2. Delete the working copy from recovery dir
3. Clean up ImageLoader and SQLite connections

On clean exit, no .swp file remains in recovery dir.

### Crash recovery

On startup, scan recovery dir for `*.bee.swp` files:

- For each .swp: extract original filename from the stem, show "Recover unsaved changes for {name}?"
- Yes → open the .swp as the source instead of the original
- No → delete the .swp

## Interaction with async loading

```
Original .bee                Recovery dir (.bee.swp)
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

The `ImageLoader` always reads from the working copy. Drains write to the working copy. No contention with the original file.

## SQLite concurrency

The working copy is accessed by:
- `ImageLoader` thread: reads blobs from `sqlar`
- Drain (main thread or dedicated thread): writes metadata to `items`, writes new blobs to `sqlar`

SQLite in WAL mode handles this cleanly — concurrent readers + one writer. Without WAL, we'd need to serialize blob reads and drain writes, but they're unlikely to overlap in practice (drain is fast).

## Disk cost

Temporary 2x file size during operation (original + working copy in recovery dir), plus a brief 3x during Save (original + working copy + temp file). For a 500MB .bee file that's 500MB–1GB extra. Photoshop users routinely eat 10x+ scratch disk costs; this is modest by comparison. The working copy is deleted on clean exit.

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
   - Recovery dir for all working copies
   - ImageLoader reads from working copy
   - Drain replaces explicit save logic
   - Save = drain + copy + atomic rename
   - Save-As = drain + copy
   - Crash recovery via recovery dir scan
   - New scene creates .swp immediately
   - Read-only files work automatically (Save disabled, Save-As works)
3. **Third**: Autosave timer + mip caching
