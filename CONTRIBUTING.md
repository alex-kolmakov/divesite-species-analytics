# Contributing to Marine Species Analytics

Thank you for your interest in contributing to Marine Species Analytics! This project combines marine biodiversity data from multiple scientific datasets to help divers and researchers discover species and dive sites.

## Ways to Contribute

### Reporting Issues

If you encounter a bug or have a feature request:

1. Check the [existing issues](https://github.com/alex-kolmakov/divesite-species-analytics/issues) to avoid duplicates
2. Create a new issue with a clear title and detailed description
3. Include steps to reproduce (for bugs) or use cases (for features)
4. Add relevant labels if possible

### Suggesting Enhancements

We welcome suggestions for:
- New data sources to integrate
- Improvements to data processing pipelines
- UI/UX enhancements for the application
- Performance optimizations
- Documentation improvements

### Code Contributions

#### Development Setup

Before contributing code, please review the documentation:
- [SETUP.md](docs/SETUP.md) - Complete setup guide
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture and data modeling
- [TESTING.md](docs/TESTING.md) - Testing guidelines
- [LOCAL_DATA_WORKFLOW.md](docs/LOCAL_DATA_WORKFLOW.md) - Local development workflow

**Prerequisites:**
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker
- gcloud CLI
- Terraform
- A GCP project with billing enabled

**Quick Setup:**
```bash
git clone https://github.com/alex-kolmakov/divesite-species-analytics.git
cd divesite-species-analytics
uv sync --all-extras
cp env.example .env  # Edit with your configuration
```

#### Development Workflow

1. **Fork the repository** and create a new branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the project structure:
   - `ingest/` - Data ingestion pipelines
   - `enrich/` - Species enrichment logic
   - `dbt/` - Data transformation models
   - `app/` - FastAPI backend and React frontend
   - `terraform/` - Infrastructure as code

3. **Follow code quality standards:**
   - Run `ruff check` for linting
   - Run `ruff format` for code formatting
   - Run `pyrefly check` for type checking
   - Ensure all tests pass with `pytest tests/`

4. **Test your changes:**
   ```bash
   # Run linting
   ruff check ingest/ enrich/ app/backend/
   ruff format --check ingest/ enrich/ app/backend/
   
   # Run type checking
   pyrefly check
   
   # Run tests
   pytest tests/
   
   # Test Docker builds if applicable
   docker build -f Dockerfile.ingest -t ingest:test .
   ```

5. **Commit your changes** with clear, descriptive commit messages:
   ```bash
   git add .
   git commit -m "feat: add support for new marine data source"
   ```

6. **Push to your fork** and create a pull request:
   ```bash
   git push origin feature/your-feature-name
   ```

#### Pull Request Guidelines

- **Title**: Use a clear, descriptive title
- **Description**: Explain what changes you made and why
- **Link issues**: Reference any related issues (e.g., "Fixes #123")
- **Tests**: Include tests for new features or bug fixes
- **Documentation**: Update documentation if you change APIs or add features
- **CI checks**: Ensure all CI checks pass before requesting review

### Code Style

This project uses:
- **Ruff** for linting and formatting
- **Pyrefly** for static type checking
- **Conventional Commits** style (optional but encouraged)

### Documentation Contributions

Documentation improvements are always welcome! This includes:
- Fixing typos or clarifying existing documentation
- Adding examples or tutorials
- Improving code comments
- Translating documentation (if applicable)

## Development Environment

### Environment Variables

Copy `env.example` to `.env` and configure:
- `GCP_PROJECT_ID` - Your GCP project ID
- `GCS_BUCKET` - Your GCS bucket name
- `BIGQUERY_DATASET` - BigQuery dataset name
- Other API keys and configuration as needed

### Running Components Locally

```bash
# Set environment variables
set -a && source .env && set +a
export GOOGLE_APPLICATION_CREDENTIALS=secret.json

# Run ingestion for a single source
uv run python -m ingest --source iucn

# Build dbt models
cd dbt && uv run dbt run && cd ..

# Run enrichment pipeline
uv run python -m enrich --new-only

# Start the application locally
uv run python -m app.backend.main
# Access at http://localhost:8080
```

## Project Structure

```
ingest/              Python CLI - downloads, transforms, uploads to GCS
enrich/              Species enrichment pipeline (GBIF + Wikipedia + Wikidata)
dbt/                 dbt models (substrate / skeleton / coral layers)
app/                 UI application (FastAPI backend + React frontend)
terraform/           GCP infrastructure as code
docs/                Setup, testing, architecture, and workflow guides
.github/workflows/   CI pipeline (lint, typecheck, Docker build, Terraform)
```

## CI/CD Pipeline

All pull requests run through automated checks:
- **Lint**: Ruff linting and format check
- **Type Check**: Pyrefly static analysis
- **Tests**: Backend pytest suite
- **Docker Build**: Build all container images
- **Terraform Validate**: Infrastructure validation

## Getting Help

- **Questions?** Open an issue with the "question" label
- **Bug reports?** Open an issue with the "bug" label
- **Feature requests?** Open an issue with the "enhancement" label

## License

By contributing to Marine Species Analytics, you agree that your contributions will be licensed under the MIT License.

## Acknowledgments

Thank you for taking the time to contribute to Marine Species Analytics! Your efforts help make marine biodiversity data more accessible to divers and researchers worldwide.
