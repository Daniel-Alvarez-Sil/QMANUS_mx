"""AgentNexus package.

Ensure `.env` is loaded as early as possible so modules that read
environment variables (like `app.config`) see the values when the
package is imported.
"""

try:
	from dotenv import load_dotenv
	from pathlib import Path
	load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
except Exception:
	# dotenv is optional; environment variables may be set externally.
	pass
