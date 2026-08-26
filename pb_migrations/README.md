# PocketBase schema

The current Animem schema is defined in `scripts/pocketbase-setup.mjs`.

The old migrations belonged to the legacy Vite/PocketBase data model and were removed. Do not commit `pb_data/`; it contains runtime data and user records.

For a fresh PocketBase instance, configure the environment variables from `.env.example` and run:

```bash
node scripts/pocketbase-setup.mjs
```
