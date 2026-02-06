# Knowledge Adapter Template

This template defines the interface for stack-knowledge backend adapters.

## Overview

Adapters allow stack-knowledge to integrate with external knowledge bases (Confluence, Notion, Sharepoint, etc.). Each adapter implements a standard interface for search and storage.

## Adapter Interface

### Required Methods

```python
class KnowledgeAdapter:
    """Base class for knowledge backend adapters."""

    def __init__(self, config: dict):
        """
        Initialize adapter with config from org.json.

        Args:
            config: The stack_knowledge section from org.json
                    e.g., {"type": "confluence", "url": "...", "space": "..."}
        """
        pass

    def search(self, query: str) -> list[KnowledgeResult]:
        """
        Search the knowledge backend.

        Args:
            query: Search query string

        Returns:
            List of KnowledgeResult objects
        """
        pass

    def add(self, knowledge: KnowledgeEntry) -> str:
        """
        Add knowledge to the backend.

        Args:
            knowledge: KnowledgeEntry object with title, type, content, etc.

        Returns:
            URL or identifier of created entry
        """
        pass

    def get(self, identifier: str) -> KnowledgeEntry:
        """
        Retrieve a specific knowledge entry.

        Args:
            identifier: URL or ID of the entry

        Returns:
            KnowledgeEntry object
        """
        pass
```

### Data Types

```python
@dataclass
class KnowledgeResult:
    """Search result from a knowledge backend."""
    title: str
    summary: str
    url: str
    source: str  # e.g., "confluence", "notion"
    relevance: float  # 0.0 to 1.0

@dataclass
class KnowledgeEntry:
    """A knowledge entry to store or retrieve."""
    title: str
    type: str  # client, project, product, domain, reference
    summary: str
    content: str
    source: str | None = None
    url: str | None = None
    metadata: dict | None = None
```

## Configuration

Adapters are configured in `org.json`:

```json
{
  "stack_knowledge": {
    "type": "confluence",
    "url": "https://acme.atlassian.net/wiki",
    "space": "ENG",
    "auth": {
      "type": "api_token",
      "env_var": "CONFLUENCE_API_TOKEN"
    }
  }
}
```

### Authentication

Adapters should support multiple auth methods:

| Auth Type | Config | Notes |
|-----------|--------|-------|
| `api_token` | `env_var` pointing to token | Most common |
| `oauth` | OAuth flow config | For user-context access |
| `service_account` | Service credentials | For automated access |

**Never store credentials in org.json.** Use environment variables or secure credential stores.

## Example: Confluence Adapter

```python
class ConfluenceAdapter(KnowledgeAdapter):
    def __init__(self, config: dict):
        self.url = config["url"]
        self.space = config["space"]
        self.token = os.environ.get(config["auth"]["env_var"])

    def search(self, query: str) -> list[KnowledgeResult]:
        # Use Confluence CQL to search
        cql = f'space = "{self.space}" AND text ~ "{query}"'
        response = self._api_call(f"/wiki/rest/api/search?cql={cql}")

        return [
            KnowledgeResult(
                title=r["title"],
                summary=r["excerpt"],
                url=f'{self.url}{r["url"]}',
                source="confluence",
                relevance=r.get("score", 0.5)
            )
            for r in response["results"]
        ]

    def add(self, knowledge: KnowledgeEntry) -> str:
        # Create Confluence page
        payload = {
            "type": "page",
            "title": knowledge.title,
            "space": {"key": self.space},
            "body": {
                "storage": {
                    "value": self._markdown_to_confluence(knowledge.content),
                    "representation": "storage"
                }
            }
        }
        response = self._api_call("/wiki/rest/api/content", method="POST", data=payload)
        return f'{self.url}/wiki{response["_links"]["webui"]}'
```

## Contributing an Adapter

1. **Fork** the gruntwork-marketplace repository
2. **Create** your adapter in `plugins/lastmilefirst/adapters/[backend]-adapter/`
3. **Implement** the `KnowledgeAdapter` interface
4. **Test** with a real backend instance
5. **Document** configuration requirements
6. **Submit** a pull request

### Adapter Checklist

- [ ] Implements all required methods
- [ ] Handles authentication securely (no hardcoded credentials)
- [ ] Includes error handling for API failures
- [ ] Documents required configuration
- [ ] Includes example org.json config
- [ ] Tested with real backend

## Planned Adapters

| Backend | Priority | Maintainer |
|---------|----------|------------|
| Confluence | High | Seeking contributor |
| Notion | High | Seeking contributor |
| Sharepoint | Medium | Seeking contributor |
| Google Docs | Medium | Seeking contributor |
| Obsidian | Low | Seeking contributor |

**Interested in contributing?** Open an issue on the gruntwork-marketplace repo.
