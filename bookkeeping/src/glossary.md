# Glossary

| Term | Definition |
| --- | --- |
| **Ack quorum (`Qa`)** | The number of bookie acknowledgements a writer must receive before an [entry](./protocol/entries.md) is considered committed. Determines durability vs. latency. `Qa ≤ Qw`. |
| **Bookie** | An individual BookKeeper storage server. Holds *fragments* of ledgers via a journal (write path) and ledger storage (read path). |
| **Ensemble (`E`)** | The ordered set of bookies across which a ledger's entries are striped. |
| **Ensemble change** | Replacing a failed bookie mid-write by recording a new ensemble *fragment* in metadata from a given entry id onward. |
| **Entry** | The atomic, append-only record in a ledger: ledger id, entry id, last-confirmed, data, digest. |
| **Entry log** | The file(s) in ledger storage into which entries from many ledgers are interleaved for the read path. |
| **Fencing** | Marking a ledger so bookies reject further adds from the old writer; prevents split-brain during recovery. |
| **Fragment** | A contiguous range of a ledger stored on one specific ensemble; metadata holds an ordered list of fragments. |
| **Journal** | The per-bookie write-ahead log; entries are fsync'd here before being acknowledged. |
| **Last-Add-Confirmed (`LAC`)** | The highest entry id confirmed by `≥ Qa` bookies; the boundary up to which regular readers may read. |
| **Ledger** | An ordered, append-only, single-writer sequence of entries. Lifecycle: `OPEN → IN_RECOVERY → CLOSED`. |
| **Metadata store** | ZooKeeper (or etcd): holds ledger metadata and live bookie membership. |
| **Recovery** | Opening an unclosed ledger after a writer crash, fencing it, fixing the last entry id, and closing it. |
| **Single-writer** | The rule that a ledger has exactly one writer at a time, giving gap-free total order. |
| **Striping** | Distributing consecutive entries across different bookies of the ensemble (entry `e` → bookies starting at `e mod E`). |
| **Write quorum (`Qw`)** | The number of bookies each entry is written to (its replication factor). `Qw ≤ E`. |
| **Decision stream** | *(Service term)* A long-lived, logical sequence of decision records, implemented as a sequence of ledgers. |
| **Decision record** | *(Service term)* One immutable entry in a decision stream capturing a decision and its context. |
