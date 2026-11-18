# CloudCost Pilot
> **Monitor. Analyze. Optimize. Every Cloud Euro Counts.**

**CloudCost Pilot** is an open-source, production-minded Cloud Cost Monitoring , Analysis & Optimization Platform built for DevOps, Cloud, and FinOps engineers. It helps teams understand actual AWS spending, discover infrastructure resources, analyze utilization metrics, and generate actionable cost optimization recommendations.

---

## Architecture & Data Flow

```text
                    AWS ACCOUNT
                         |
        +----------------+----------------+
        |                |                |
   AWS Cost Explorer    EC2              EBS
        |                |                |
        |             EC2 API          EC2 API
        |                |                |
        +----------------+----------------+
                         |
                    CloudWatch
                         |
                         |
                 PYTHON BACKEND
                         |
             +-----------+-----------+
             |                       |
       Cost Collector          Resource Scanner
             |                       |
             +-----------+-----------+
                         |
                 ANALYSIS ENGINE
                         |
             +-----------+-----------+
             |                       |
       Optimization             Anomaly
         Engine                Detection
             |                       |
             +-----------+-----------+
                         |
                    PostgreSQL
                         |
             +-----------+-----------+
             |                       |
          Grafana               Notification
         Dashboard               Service
             |                       |
             |                   Email/Slack
             |
       Cost & Resource
         Analytics
```

---

## Current Status: Phase 1 — AWS Cost Data Collection

Phase 1 focuses on actual AWS Cost Explorer data collection, caller identity validation, service-level cost breakdown, daily trend analysis, and atomic JSON export.

### Features Implemented:
- [x] **AWS Identity & Credential Validation**: Validates AWS credentials using `STS GetCallerIdentity` before executing API calls.
- [x] **AWS Cost Explorer Integration**: Connects to the global billing endpoint (`us-east-1`) via Boto3 with exponential backoff retry.
- [x] **Flexible Granularity**: Supports `DAILY` and `MONTHLY` cost aggregation for custom or automated date ranges.
- [x] **Service-Level Cost Breakdown**: Automatically groups costs by `SERVICE` dimension, calculating proportional contribution percentages.
- [x] **Pagination Handling**: Full automatic pagination traversal for multi-page Cost Explorer results.
- [x] **Decimal Financial Accuracy**: Preserves exact AWS-reported decimal strings and uses Python `Decimal` to avoid binary floating-point rounding errors.
- [x] **Currency Preservation**: Retains original billing currency reported by AWS.
- [x] **Trend & Anomaly Analysis**: Computes day-over-day cost delta and flags spending spikes exceeding baseline thresholds.
- [x] **Atomic JSON Export**: Atomically writes billing extracts to disk using temporary file swapping to prevent partial writes.
- [x] **Structured Logging**: Provides JSON-formatted logging for automated environments and human-readable text for CLI, with automatic redaction of sensitive credentials.
- [x] **Least-Privilege Security**: Fully read-only IAM policy with strict prohibition of destructive API actions.
- [x] **Automated Test Suite**: 100% mocked unit tests using `botocore.stub.Stubber` — runnable locally and in CI without an active AWS account or billable infrastructure.

---

## Technology Stack

| Technology | Role | Status |
|---|---|---|
| **Python 3.12** | Core backend logic, analysis, and CLI | Implemented |
| **Boto3** | AWS SDK for Python | Implemented |
| **AWS Cost Explorer** | Source of actual cost and usage data | Implemented |
| **Pytest & Coverage** | Automated unit and safety tests | Implemented |
| **Ruff** | Code formatting and linting | Implemented |
| **Pydantic v2** | Data validation and domain models | Implemented |
| **PostgreSQL** | Historical cost & inventory persistence | Phase 6 |
| **Grafana** | Centralized financial dashboards | Phase 6 |
| **Docker & Compose** | Containerized local environment | Phase 7 |
| **Terraform** | Infrastructure as Code | Phase 7 |
| **GitHub Actions** | Automated CI/CD pipeline | Phase 7 |

---

## Quickstart & Installation

### Prerequisites
- Python 3.12+
- AWS CLI configured (optional if running mocked tests)

### 1. Clone & Set Up Virtual Environment

```bash
cd cloudcost-pilot
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

### 2. Configure Environment

Copy the template configuration:
```bash
cp .env.example .env
```

Edit `.env` if using a named AWS profile:
```dotenv
AWS_PROFILE=cloudcost-pilot
AWS_DEFAULT_REGION=us-east-1
LOG_LEVEL=INFO
LOG_FORMAT=text
```

---

## Usage

### 1. Run Daily Cost Collection

```bash
# Using default date range (current month-to-date)
python scripts/collect_costs.py --granularity DAILY

# Using specific date range (start inclusive, end exclusive)
python scripts/collect_costs.py \
  --start 2026-11-01 \
  --end 2026-11-14 \
  --granularity DAILY \
  --profile cloudcost-pilot \
  --output data/costs_daily.json
```

### 2. Run Monthly Cost Collection

```bash
# Using default date range (last 3 months)
python scripts/collect_costs.py --granularity MONTHLY

# Using specific monthly date range
python scripts/collect_costs.py \
  --start 2026-08-01 \
  --end 2026-11-01 \
  --granularity MONTHLY \
  --output data/costs_monthly.json
```

### 3. Example Console Output

```text
======================================================================
 CloudCost Pilot — AWS Cost Explorer Collector
======================================================================
 Reporting Period: 2026-11-01 to 2026-11-14 (exclusive)
 Granularity:      DAILY
 Metric:           UnblendedCost
 Profile:          cloudcost-pilot
 Output Target:    data/costs_daily.json
----------------------------------------------------------------------
 Connected Account: 123456789012
 Caller Identity:   arn:aws:iam::123456789012:user/finops-reader
----------------------------------------------------------------------
 Querying AWS Cost Explorer API...

======================================================================
 COLLECTION SUMMARY
======================================================================
 Total Recorded Cost: 90.0000 USD
 Time Periods:        13
 Highest Cost Service: Amazon Elastic Compute Cloud - Compute (45.0000 USD)

 Top 5 Services by Spending:
  1. Amazon Elastic Compute Cloud - Compute       45.0000 USD ( 50.0%)
  2. Amazon Relational Database Service           22.0000 USD ( 24.4%)
  3. Amazon Simple Storage Service                 8.0000 USD (  8.9%)
  4. AmazonCloudWatch                              5.0000 USD (  5.6%)
  5. AWS Lambda                                    3.0000 USD (  3.3%)
----------------------------------------------------------------------
 Results successfully exported to: data/costs_daily.json
======================================================================
```

---

## Security Model & IAM Permissions

CloudCost Pilot follows strict **read-only** and **least-privilege** security principles.

- **Zero Destructive Actions**: The platform cannot terminate EC2 instances, delete EBS volumes, modify security groups, or alter infrastructure.
- **Dedicated IAM Policy**: Available in [`docs/iam_policy.json`](docs/iam_policy.json).
- See detailed security documentation in [`docs/IAM_PERMISSIONS.md`](docs/IAM_PERMISSIONS.md).

---

## Running Tests & Linting

All unit tests use mocked AWS responses and do not require live AWS credentials or incur AWS charges.

```bash
# Run tests with coverage
make test

# Run Ruff linter
make lint

# Run Ruff code formatter
make format
```

---

## Roadmap

- [x] **Phase 1 — AWS Cost Data Collection** (Current)
- [ ] **Phase 2 — Resource Discovery** (EC2, EBS inventory, CloudWatch metrics)
- [ ] **Phase 3 — Optimization Engine** (Underutilized rules, unattached storage estimates)
- [ ] **Phase 4 — Automation & Scheduling** (Linux Cron, idempotent jobs, failure visibility)
- [ ] **Phase 5 — Budgets & Anomaly Alerts** (Thresholds, Slack / Email alerts)
- [ ] **Phase 6 — Data Persistence & Dashboards** (PostgreSQL schema, Grafana dashboards)
- [ ] **Phase 7 — Production Engineering** (Docker Compose, Terraform IaC, GitHub Actions CI/CD)
