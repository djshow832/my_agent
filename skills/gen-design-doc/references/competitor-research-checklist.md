# Competitor Research Checklist

Use competitor research only when it helps evaluate a concrete TiProxy design choice.

## Prefer These Sources

- Official product documentation
- Public architecture docs
- Source code or public design docs when available
- Release notes only when behavior changed recently

## Focus Areas

- Connection lifecycle and multiplexing
- Read or write routing
- Failover and health checking
- Session stickiness and transaction handling
- Load balancing policy
- Authentication and TLS handling
- Configuration model and safety rails
- Observability and admin interfaces

## Candidate Systems

- ProxySQL
- MariaDB MaxScale
- Amazon Aurora Proxy or RDS Proxy
- PolarDB Proxy

## Output Pattern

For each relevant system, capture:

- What it does
- Why that design exists
- What tradeoff it makes
- Whether the pattern fits TiProxy
- Why the final proposal still chooses a different direction, if applicable

Avoid broad surveys. Compare only the features that materially affect the proposal.
