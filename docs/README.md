# apibackuper documentation

This directory contains the Docusaurus documentation site for apibackuper.

## Development

### Prerequisites

- Node.js 20+ and npm (the locked Docusaurus release requires Node 20)

### Installation

```bash
cd docs
npm ci
```

### Local development

Start the development server:

```bash
npm start
```

This starts a local development server and opens a browser window. Most changes
are reflected live without restarting the server. From the repository root you
can also run `make docs-serve`.

### Build

Build the site for production:

```bash
npm run build
```

This generates static content into the `build` directory. From the repository
root you can also run `make docs`.

### Serve

Serve the built site locally:

```bash
npm run serve
```

## Project structure

```
docs/
├── docusaurus.config.js    # Docusaurus configuration
├── sidebars.js             # Sidebar navigation
├── package.json            # Node.js dependencies
├── babel.config.js         # Babel configuration
├── src/
│   ├── css/custom.css      # Custom styles
│   ├── pages/index.js      # Homepage (documentation contents)
│   └── components/         # React components
├── static/img/             # Logo and favicon
└── docs/                   # Documentation content
    ├── getting-started/    # Installation, quick start, cookbook
    ├── use-cases/          # End-to-end examples
    ├── commands/           # CLI reference
    ├── configuration/      # YAML/INI project configuration
    ├── examples/           # Sample projects and templates
    ├── development/        # Contributing and community
    └── license.md
```

## Deployment

The documentation is deployed to GitHub Pages at
[ruarxive.org/apibackuper](https://ruarxive.org/apibackuper/) when
documentation changes are pushed to `master` or `main`, or the workflow is
started manually. The workflow lives in
`.github/workflows/deploy-docs.yml`.

### GitHub Pages setup

1. Open the repository settings on GitHub.
2. Navigate to **Pages**.
3. Under **Source**, select **GitHub Actions**.

See `GITHUB_PAGES_SETUP.md` for details.

## Documentation structure

- **Getting Started**: Installation, quick start, positioning, cookbook
- **Use Cases**: Full backups, incremental updates, follow requests, exports
- **CLI Reference**: Command-by-command documentation
- **Configuration**: YAML/INI sections, pagination, auth, storage, hooks
- **Examples**: Working projects and starter templates
- **Development**: Contributing, tests, community

## Contributing

When adding or updating documentation:

1. Edit the markdown files in `docs/docs/`.
2. Follow the existing frontmatter (`title`, `description`).
3. Check flags against `python -m apibackuper <command> --help` and behavior
   against the current implementation and schema.
4. Update the root `README.md` and `CHANGELOG.md` when user-facing behavior changes;
   keep unreleased work under `Unreleased` without changing release metadata.
5. Validate examples from the repository root with `python -m scripts.validate_examples`.
   If you edited a page listed in `scripts/build_llms_full.py`, regenerate
   `static/llms-full.txt` with `python -m scripts.build_llms_full`;
   `tests/test_llms_full.py` fails while it is stale.
6. Run `python -m pytest --no-cov tests/test_docs_examples.py` from the repository
   root. It executes the marked Quick Start, completeness, GET/POST use-case,
   export and Python API snippets against a local server, checks the resulting
   archives/exports, and exercises the documented integrity checks on invalid data.
7. Preview with `npm start` and confirm `npm run build` succeeds. Broken site
   and Markdown links fail the build. CI also builds the site on pull requests.

`scripts.validate_examples` checks complete shipped YAML configs, JSON files,
and YAML/JSON blocks in user-facing Markdown. Fragments may omit required keys
but must use known fields with correct types. Mark complete configurations
`yaml config` to require every mandatory field. Mark executable walkthrough fences
with `bash doc-test` or `python doc-test`; the walkthrough test owns setup and
executes marked blocks sequentially. External API samples are not fetched in CI.

Edit source Markdown only; `build/` and `.docusaurus/` are generated and ignored.
