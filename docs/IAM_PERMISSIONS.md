# CloudCost Pilot — AWS IAM Permissions and Security Model

## 1. Security Principles

CloudCost Pilot enforces strict security and cost control principles:

1. **Least Privilege & Read-Only**: The platform operates in observation and analytical mode. It only requires read permissions.
2. **Explicit Prohibition of Destructive Actions**: The IAM policy explicitly **excludes** any permissions for:
   - Terminating EC2 instances (`ec2:TerminateInstances`)
   - Stopping EC2 instances (`ec2:StopInstances`)
   - Deleting EBS volumes (`ec2:DeleteVolume`)
   - Modifying instance types or storage configurations (`ec2:ModifyInstanceAttribute`)
   - Deleting snapshots or backups
3. **No Hardcoded Credentials**: Authentication leverages standard AWS credential resolution:
   - Local development: Named AWS CLI profiles (`~/.aws/credentials`) or short-lived SSO credentials.
   - Production / Hosted: AWS IAM Roles and STS AssumeRole / Instance Profiles.
4. **Data Isolation**: Cost Explorer endpoint is global and accessed via `us-east-1`, separate from regional resource scanning.

---

## 2. Required Permissions by Implementation Phase

### Phase 1: Cost Data Collection (Current Phase)
| Action | Purpose | Scope |
|---|---|---|
| `ce:GetCostAndUsage` | Retrieve daily and monthly cost data with service grouping | Account billing data |
| `ce:GetDimensionValues` | Query dimension values (e.g. AWS services) | Cost Explorer metadata |
| `sts:GetCallerIdentity` | Validate authentication and retrieve AWS Account ID and ARN | Caller identity check |

### Phase 2: Resource Discovery & Metrics (Upcoming)
| Action | Purpose | Scope |
|---|---|---|
| `ec2:DescribeInstances` | Discover EC2 instance inventory, states, and types | Regional compute inventory |
| `ec2:DescribeVolumes` | Discover EBS volume sizes, types, and attachment states | Regional block storage |
| `ec2:DescribeRegions` | Discover active AWS regions for scanning | Global region metadata |
| `ec2:DescribeTags` | Retrieve resource tags for cost attribution | Regional tag metadata |
| `cloudwatch:GetMetricData` | Retrieve CPU utilization metrics for EC2 instances | Resource metrics |
| `cloudwatch:GetMetricStatistics` | Retrieve average and maximum CPU statistics over evaluation windows | Metric statistics |

---

## 3. How to Configure IAM in AWS

### Option A: Using AWS CLI (Recommended)

1. Create the IAM policy:
```bash
aws iam create-policy \
  --policy-name CloudCostPilotReadOnlyPolicy \
  --policy-document file://docs/iam_policy.json \
  --description "Least-privilege read-only policy for CloudCost Pilot"
```

2. Attach the policy to an IAM user, group, or role:
```bash
# Example for an IAM user:
aws iam attach-user-policy \
  --user-name <YOUR_IAM_USER> \
  --policy-arn arn:aws:iam::<YOUR_ACCOUNT_ID>:policy/CloudCostPilotReadOnlyPolicy
```

### Option B: Local Named Profile Setup

Configure a local AWS CLI named profile:
```bash
aws configure --profile cloudcost-pilot
# Enter Access Key ID, Secret Access Key, and default region (e.g., us-east-1)

# Verify credentials and identity:
aws sts get-caller-identity --profile cloudcost-pilot
```

Test with CloudCost Pilot:
```bash
python scripts/collect_costs.py --profile cloudcost-pilot
```
