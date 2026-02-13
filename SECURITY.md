# Security Policy

## Reporting Security Vulnerabilities

The Marine Species Analytics project takes security seriously. We appreciate your efforts to responsibly disclose any security vulnerabilities you find.

### Reporting Process

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report security vulnerabilities by:

1. **Via GitHub**: Use the "Security" tab in the repository to report a vulnerability privately
2. **Via Email**: Contact the maintainer directly via the contact information in their [GitHub profile](https://github.com/alex-kolmakov)
3. **Via LinkedIn**: Message [Aleksandr Kolmakov](https://linkedin.com/in/aleksandr-kolmakov)

Please include the following information in your report:

- Type of vulnerability
- Full paths of source file(s) related to the manifestation of the vulnerability
- The location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

### What to Expect

- **Acknowledgment**: We will acknowledge receipt of your vulnerability report within 48 hours
- **Assessment**: We will assess the vulnerability and determine its severity and impact
- **Fix Timeline**: We will work on a fix and keep you informed of our progress
- **Disclosure**: Once the fix is deployed, we will publicly disclose the vulnerability (with your permission)

## Supported Versions

Currently, security updates are provided for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| < 1.0   | :x:                |

**Note**: As this is an active development project, we recommend always using the latest version from the `main` branch.

## Security Considerations

### API Keys and Credentials

This project requires various API keys and credentials for operation:

- **GCP Service Account Keys**: Should never be committed to the repository
- **API Keys**: GBIF, Wikipedia, Wikidata, PADI API keys should be stored in `.env` or secret manager
- **Environment Variables**: Use `env.example` as a template, never commit actual `.env` files

**Best Practices**:
- Store credentials in environment variables or GCP Secret Manager
- Use service accounts with minimal required permissions
- Rotate API keys regularly
- Never commit `secret.json`, `.env`, or other credential files to version control

### Data Privacy

This project processes marine biodiversity data from public sources:

- **OBIS, GBIF, WoRMS**: Public scientific datasets
- **PADI dive sites**: Publicly available locations
- **Species information**: Public domain scientific data

The application does not collect or store user data beyond standard web server logs.

### Infrastructure Security

The project deploys to Google Cloud Platform:

- **Cloud Run**: Runs containerized applications with least-privilege service accounts
- **BigQuery**: Stores processed data with appropriate access controls
- **Cloud Storage**: Stores parquet files with bucket-level permissions
- **Terraform**: Manages infrastructure with state stored securely

**Recommendations**:
- Use separate GCP projects for production and development
- Enable VPC Service Controls if handling sensitive data
- Regularly review IAM permissions
- Enable audit logging for all services

### Dependency Security

This project uses:
- **Python dependencies**: Managed via `uv` with lock file
- **Docker base images**: Based on official Python images
- **GitHub Actions**: For CI/CD

**Security Practices**:
- Dependencies are pinned in `uv.lock`
- Regular dependency updates via Dependabot (recommended)
- Docker images built from verified base images
- CI/CD pipeline includes security checks

### Common Vulnerabilities

Areas to be mindful of:

1. **SQL Injection**: All BigQuery queries use parameterized queries via dbt
2. **Path Traversal**: File operations validate paths and use absolute paths
3. **API Rate Limiting**: External API calls implement rate limiting and backoff
4. **Container Security**: Docker images use non-root users where possible
5. **Secrets in Logs**: Logging configured to avoid exposing credentials

## Security Updates

Security fixes will be:
- Released as soon as possible after verification
- Documented in release notes and commit messages
- Announced via GitHub Security Advisories

## Compliance

This project:
- Uses data from public scientific sources
- Does not collect personal information from users
- Follows GCP security best practices
- Implements industry-standard security measures for cloud applications

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Google Cloud Security Best Practices](https://cloud.google.com/security/best-practices)
- [Container Security Best Practices](https://cloud.google.com/architecture/best-practices-for-building-containers)

## Questions?

If you have questions about security but don't have a vulnerability to report, please:
- Open a GitHub issue with the "question" label
- Reach out via the contact methods listed above

Thank you for helping keep Marine Species Analytics secure!
