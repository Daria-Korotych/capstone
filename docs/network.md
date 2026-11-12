# Network

```mermaid
flowchart TB
    Internet((Internet))
    IGW[Internet Gateway]
    subgraph VPC["VPC 10.20.0.0/16"]
        subgraph AZA["us-east-1a"]
            PUB1["kv-dev-public-1<br/>10.20.0.0/24"]:::public
            PRIV1["kv-dev-private-1<br/>10.20.10.0/24"]:::private
        end
        subgraph AZB["us-east-1b"]
            PUB2["kv-dev-public-2<br/>10.20.1.0/24"]:::public
            PRIV2["kv-dev-private-2<br/>10.20.11.0/24"]:::private
        end
        RTPUB["Public route table<br/>10.20.0.0/16 → local<br/>0.0.0.0/0 → IGW"]
        RTPRIV["Private route table<br/>10.20.0.0/16 → local"]
    end
    PUB1 --- RTPUB
    PUB2 --- RTPUB
    PRIV1 --- RTPRIV
    PRIV2 --- RTPRIV
    RTPUB -->|"0.0.0.0/0"| IGW
    IGW --> Internet

    classDef public fill:#c8f7c5,stroke:#2e7d32,color:#000
    classDef private fill:#f7c5c5,stroke:#c62828,color:#000
```

Public-підмережі (зелені) мають маршрут `0.0.0.0/0` через Internet Gateway, тому ресурси в них можуть виходити в інтернет. Private-підмережі (червоні) мають лише локальний маршрут `10.20.0.0/16 → local`: вони не мають доступу до інтернету і недосяжні ззовні. NAT Gateway свідомо не створюється: він платний, а ресурсам у private-підмережах зовнішній доступ не потрібен (див. [ADR-0004](adr/0004-cidr-scheme.md)).

