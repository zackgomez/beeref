USER_VERSION = 3
APPLICATION_ID = 2060242126


SCHEMA = [
    """
    CREATE TABLE items (
        id INTEGER PRIMARY KEY,
        type TEXT NOT NULL,
        x REAL DEFAULT 0,
        y REAL DEFAULT 0,
        z REAL DEFAULT 0,
        scale REAL DEFAULT 1,
        rotation REAL DEFAULT 0,
        flip INTEGER DEFAULT 1,
        data JSON,
        width INTEGER,
        height INTEGER
    )
    """,
    """
    CREATE TABLE sqlar (
        name TEXT PRIMARY KEY,
        item_id INTEGER NOT NULL UNIQUE,
        mode INT,
        mtime INT default current_timestamp,
        sz INT,
        data BLOB,
        FOREIGN KEY (item_id)
          REFERENCES items (id)
             ON DELETE CASCADE
             ON UPDATE NO ACTION
    )
    """,
]


def _populate_image_dimensions(io):
    """Read image headers from sqlar blobs to populate width/height."""
    from io import BytesIO
    from PIL import Image

    rows = io.fetchall("SELECT item_id, data FROM sqlar")
    for item_id, blob in rows:
        try:
            img = Image.open(BytesIO(blob))
            w, h = img.size
            io.ex("UPDATE items SET width=?, height=? WHERE id=?", (w, h, item_id))
        except Exception:
            pass


MIGRATIONS = {
    2: [
        lambda io: io.ex("ALTER TABLE items ADD COLUMN data JSON"),
        lambda io: io.ex("UPDATE items SET data = json_object('filename', filename)"),
    ],
    3: [
        lambda io: io.ex("ALTER TABLE items ADD COLUMN width INTEGER"),
        lambda io: io.ex("ALTER TABLE items ADD COLUMN height INTEGER"),
        _populate_image_dimensions,
    ],
}
