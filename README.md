# bd-copyrights

A tool to find and optionally populate missing copyright statements for components in a [Black Duck](https://www.blackducksoftware.com/) Bill of Materials (BOM).

Many BOM components have zero copyright statements recorded against them in Black Duck. This tool works through the BOM in three phases to recover copyrights from alternative sources, and can optionally write those copyrights back to Black Duck.

---

## How it works

### Phase 1 — Copyright count audit
All active (non-ignored) BOM components are checked asynchronously for their existing copyright count. Components with at least one copyright are left untouched.

### Phase 2 — Alternative origin search
For each component with zero copyrights (or all components when `--all_copyrights` is set), the tool searches every alternative origin registered against the component in Black Duck for copyright text (via the origins API).

### Phase 3 — Local source tree scan (optional)
For components that still have no copyrights after Phase 2, the tool searches the project's signature scan source trees for copyright string matches. This phase can be skipped with `--skip_local_copyrights`.

### Update (optional)
If `--update_copyrights` is specified, all copyright texts found in Phases 2 and 3 are POSTed back to Black Duck against the relevant component origins.

A summary of results is printed at the end of each run.

---

## Requirements

- Python 3.8 or later
- A Black Duck instance accessible over HTTPS
- A Black Duck API token with read access to the target project (and write access if using `--update_copyrights`)

### Dependencies

```
blackduck>=1.1.3
requests
aiohttp
asyncio
```

Install dependencies:

```bash
pip install .
```

---

## Usage

```
python bd_kernel_vulns/main.py [options]
```

### Required arguments

| Argument | Environment variable | Description |
|---|---|---|
| `--blackduck_url URL` | `BLACKDUCK_URL` | Black Duck server base URL |
| `--blackduck_api_token TOKEN` | `BLACKDUCK_API_TOKEN` | Black Duck API token |
| `-p PROJECT` / `--project PROJECT` | — | Black Duck project name |
| `-v VERSION` / `--version VERSION` | — | Black Duck project version name |

CLI arguments take precedence over environment variables.

### Optional arguments

| Argument                  | Description                                                                     |
|---------------------------|---------------------------------------------------------------------------------|
| `--blackduck_trust_cert`  | Disable TLS certificate verification (also set via `BLACKDUCK_TRUST_CERT=true`) |
| `--all_copyrights`        | Process all components in Phases 2 and 3, not just those with zero existing copyrights |
| `--update_copyrights`     | POST discovered copyrights back to Black Duck (default: read-only/dry run)      |
| `--skip_local_copyrights` | Skip Phase 3 source tree scan                                                   |
| `--logfile FILE`          | Write log output to FILE in addition to stdout                                  |
| `--report`                | List all discovered copyrights per component                                    |
| `--debug`                 | Enable debug-level logging                                                      |

---

## Examples

**Dry run — find missing copyrights without writing anything back:**
```bash
python bd_kernel_vulns/main.py \
  --blackduck_url https://my-blackduck-server.example.com \
  --blackduck_api_token <token> \
  -p "My Project" \
  -v "1.0"
```

**Update copyrights in Black Duck:**
```bash
python bd_kernel_vulns/main.py \
  --blackduck_url https://my-blackduck-server.example.com \
  --blackduck_api_token <token> \
  -p "My Project" \
  -v "1.0" \
  --update_copyrights
```

**Process all components (not just those missing copyrights) and update Black Duck:**
```bash
python bd_kernel_vulns/main.py \
  --blackduck_url https://my-blackduck-server.example.com \
  --blackduck_api_token <token> \
  -p "My Project" \
  -v "1.0" \
  --all_copyrights \
  --update_copyrights
```

**Using environment variables and skipping the source tree scan:**
```bash
export BLACKDUCK_URL=https://my-blackduck-server.example.com
export BLACKDUCK_API_TOKEN=<token>

python bd_kernel_vulns/main.py \
  -p "My Project" \
  -v "1.0" \
  --skip_local_copyrights \
  --update_copyrights
```

**Write logs to a file:**
```bash
python bd_kernel_vulns/main.py \
  -p "My Project" \
  -v "1.0" \
  --logfile run.log \
  --debug
```

---

## Output

The tool logs progress to stdout (and optionally to a log file). At the end of each run a summary is printed, for example:

```
PROJECT STATUS:
  - 120 active components in project
  - 34 components originally with no copyrights
  - 21 components with copyrights in alternate origins
  - 8 components with local scan copyrights
  - 29 components updated with new copyrights (143 total copyrights)
```

If `--update_copyrights` is not supplied, no data is written to Black Duck and the final summary line will read:

```
  - No copyrights updated (--update_copyrights not specified)
```

---

## License

MIT
