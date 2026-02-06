# Profiles

Login profiles for auto-login. Files in this directory (except `.md` and `.gitkeep`) are **gitignored** to prevent committing credentials.

## Format

Profiles use YAML (`.yml`) format:

```yaml
# profiles/mychar.yml
username: mycharacter
password: mypassword
```

## Creating a Profile

```bash
uv run mud-client --create-profile mychar
```

This prompts for username and password (password input is hidden) and writes `profiles/mychar.yml`.

## Usage

```bash
uv run mud-client -c aardwolf -p mychar
```

The `-p`/`--profile` flag loads `profiles/<name>.yml` and automatically sends the username and password during the login sequence.

## Fields

| Field      | Required | Description                        |
|------------|----------|------------------------------------|
| `username` | yes      | Character name sent at login prompt |
| `password` | no       | Password sent when server requests it |
