# Security notes

- Copy `.env.example` to `.env` for local configuration. Never commit `.env`.
- Keep provider keys, database passwords, tunnel tokens, and connection strings out of
  source code, screenshots, logs, and issue reports.
- Rotate any credential that has been exposed in a chat, terminal capture, or public
  repository.
- Downloaded media, audio, transcripts, and exported JSON are local working files and
  are intentionally ignored by Git.
