# Code Review Rules

## Python
- Line length: 100
- Linter/Formatter: ruff
- Type checker: mypy (gradual)
- Use async/await for I/O operations
- Prefer f-strings over format() or %

## Security
- Never commit secrets, tokens, or credentials
- Validate external input at system boundaries
- No command injection via string interpolation in subprocess calls

## Style
- Keep functions focused and concise
- Minimal abstractions — no premature generalization
- Comments only where logic is not self-evident

## Testing
- Framework: pytest + pytest-asyncio
- Tests in fastapi/tests/
- Mock external services (HTTP, filesystem, subprocess)
