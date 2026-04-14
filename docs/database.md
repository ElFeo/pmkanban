# Database approach

The MVP uses SQLite with one board per user. Columns are fixed in count but can be renamed, and cards are ordered within columns.

## Core entities

- users: supports multiple users for future use
- boards: one board per user in MVP
- columns: ordered, renameable columns per board
- cards: ordered items within a column

## Ordering

Both columns and cards use an integer `position` for ordering. Moving an item updates its position in the target list.

## Schema JSON

The proposed schema is stored in schemas/myschema.json.
