# M2 architecture

Coordinator and 2 shards in one AZ, public subnet. Decision and reasons: [ADR-0008](../adr/0008-compute-and-exposure.md).

```mermaid
flowchart TB
    Op((Operator<br/>OperatorCidr))
    CI((GitHub runner<br/>CiCidr))
    IGW[Internet Gateway]
    subgraph VPC["VPC 10.20.0.0/16"]
        subgraph AZA["us-east-1a"]
            subgraph PUB1["kv-dev-public-1 · 10.20.0.0/24"]
                C["coordinator<br/>t3.micro · :8080"]:::coord
                S1["shard-1<br/>t3.micro · :8081"]:::shard
                S2["shard-2<br/>t3.micro · :8081"]:::shard
            end
            PRIV1["kv-dev-private-1 · 10.20.10.0/24<br/>empty (M3)"]:::empty
        end
        subgraph AZB["us-east-1b"]
            PUB2["kv-dev-public-2 · 10.20.1.0/24<br/>empty"]:::empty
            PRIV2["kv-dev-private-2 · 10.20.11.0/24<br/>empty (M3)"]:::empty
        end
    end
    Op -->|":8080"| IGW
    CI -->|":8080"| IGW
    IGW --> C
    C -->|":8081 · private IPs"| S1
    C -->|":8081 · private IPs"| S2
    S1 -.->|"heartbeat :8080"| C
    S2 -.->|"heartbeat :8080"| C

    classDef coord fill:#c8f7c5,stroke:#2e7d32,color:#000
    classDef shard fill:#c5d8f7,stroke:#1565c0,color:#000
    classDef empty fill:#eeeeee,stroke:#999,color:#555,stroke-dasharray: 4 3
```

## Who can talk to whom

| To | Port | Allowed from |
|---|---|---|
| coordinator | 8080 | `OperatorCidr`, `CiCidr`, shard SG (heartbeat) |
| shard-1, shard-2 | 8081 | coordinator SG only |

## Why one AZ

- Benchmark has no cross-AZ latency or transfer cost.
- Cost: if `us-east-1a` fails, everything fails. Acceptable in M2: data is in memory anyway.
- M3 spreads shard replicas over both AZs.
