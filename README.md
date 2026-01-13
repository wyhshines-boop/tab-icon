# My NewTab Assets

This repository maintains icon assets and configuration data for the NewTab extension.

## Directory Structure

```plaintext
.
├── icons/                 # High-resolution PNG icons
│   ├── bilibili.png
│   ├── github.png
│   └── ...
├── config/
│   ├── mapping.json       # Mapping from domain to icon filename
│   └── presets.json       # Default shortcuts list
└── README.md
```

## Configuration

### `config/mapping.json`

Maps domains to icon keys (filenames without extension). This allows multiple domains to share the same icon and handles specific mapping logic.

### `config/presets.json`

Defines the default shortcuts for new users. `iconKey` should match an entry in `mapping.json` or a filename in `icons/`. If `iconKey` is null, the application should fallback to the website's favicon.
