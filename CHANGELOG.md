# Changelog

All notable changes to the `mdlm` CLI project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-02-24

### Added

- **New `query` command**: Query the MarkdownLM knowledge base for documented rules, patterns, and architectural decisions across different categories (architecture, stack, testing, deployment, security, style, dependencies, error_handling, business_logic, general).
  - Usage: `mdlm query "How should errors be handled?" --category error_handling`
  - Returns matching documentation with automatic detection of knowledge gaps

- **New `validate` command**: Validate code snippets against your team's documented rules and standards.
  - Usage: `mdlm validate path/to/code.ts --task "Creates POST /users endpoint" --category security`
  - Accepts both file paths and inline code
  - Displays violations, rule details, and fix suggestions
  - Performs validation across architectural, style, security, and business logic rules

- **New `resolve-gap` command**: Detect and log undocumented architectural or design decisions.
  - Usage: `mdlm resolve-gap "Which HTTP client should we use?" --category dependencies`
  - Integrates with your team's gap resolution policy (ask_user, infer, or agent_decide)
  - Helps surface missing documentation that needs to be added to the knowledge base

### Implementation Details

These three new commands implement the complete governance toolkit from the MarkdownLM MCP (Model Context Protocol) server, bringing the same validation and knowledge base querying capabilities to the CLI that are available to AI coding agents.

All commands are fully integrated with the existing MarkdownLM API and respect the authenticated user's knowledge base permissions.

## [0.1.0] - Initial Release

### Added

- **`configure` command**: Securely save your MarkdownLM API key to `~/.config/mdlm/config` (permissions: 0600)
- **`clone` command**: Download your entire knowledge base or a specific category to `./knowledge/` with manifest tracking
- **`pull` command**: Refresh docs from the server, overwriting local copies with latest remote versions
- **`status` command**: Show local changes (new, modified, deleted files) vs the server using content hashing
- **`push` command**: Upload local changes back to the server with conflict detection and version management

### Security

- API keys stored securely with 0600 permissions
- HTTPS enforced; HTTP URLs rejected
- Conflict detection on push operations
- Safe-by-default: `--delete` flag required to remove remote docs

### Features

- Support for all 10 knowledge base categories
- Automatic category inference from directory structure
- Content hash-based change detection
- Version conflict resolution
- Configuration via `~/.config/mdlm/config` or `MDLM_API_KEY` environment variable
