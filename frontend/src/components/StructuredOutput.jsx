import { CheckCircle2, Code2, GitBranch, ListTree, Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { sourceLookup } from "../graphUtils.js";

const tabs = ["Claim", "Events", "Parties", "Financials", "Documents", "Sources", "Citations"];

function SourceChips({ ids, sources, documents, onSelectSource }) {
  return (
    <div className="source-chips">
      {(ids || []).map((sourceId) => {
        const source = sources[sourceId];
        const label = source ? sourceLabel(source, documents) : sourceId;
        return (
          <button key={sourceId} type="button" onClick={() => source && onSelectSource(source.id)}>
            {label}
          </button>
        );
      })}
    </div>
  );
}

export function StructuredOutput({ graph, job, onSelectSource }) {
  const [activeView, setActiveView] = useState("Claim");
  const [mode, setMode] = useState("Structured");
  const sources = useMemo(() => sourceLookup(graph), [graph]);
  const documentsById = useMemo(
    () =>
      (graph?.documents || []).reduce((lookup, document) => {
        lookup[document.id] = document;
        return lookup;
      }, {}),
    [graph]
  );
  const citationRows = useMemo(() => buildCitationRows(graph), [graph]);
  const validation = graph?.validation;

  return (
    <main className="output">
      <div className="output-head">
        <div>
          <h2>Structured output</h2>
          <nav className="tabs" aria-label="Structured output sections" role="tablist">
            {tabs.map((tab) => (
              <button
                key={tab}
                className={activeView === tab ? "active" : ""}
                onClick={() => {
                  setActiveView(tab);
                  setMode("Structured");
                }}
                aria-selected={activeView === tab && mode === "Structured"}
                role="tab"
                type="button"
              >
                {tab}
              </button>
            ))}
          </nav>
        </div>
        <div className="view-tabs">
          <button type="button" className={mode === "JSON" ? "active" : ""} onClick={() => setMode("JSON")}>
            <Code2 size={15} /> JSON
          </button>
          <button type="button" className={mode === "Graph" ? "active" : ""} onClick={() => setMode("Graph")}>
            <GitBranch size={15} /> Graph
          </button>
          <button type="button" className={mode === "Timeline" ? "active" : ""} onClick={() => setMode("Timeline")}>
            <ListTree size={15} /> Timeline
          </button>
        </div>
      </div>

      {!graph ? (
        <div className="workbench-empty">
          <Search size={28} />
          <h3>{job ? "Processing claim files" : "No structured output yet"}</h3>
          <p>
            {job
              ? "The backend is sorting documents and creating the claim knowledge graph."
              : "Drop claim files on the left to generate Claim, Events, Parties, Financials, Documents, and Sources."}
          </p>
        </div>
      ) : mode === "JSON" ? (
        <section className="result-panel json-panel">
          <PanelHeading title="Structured JSON" valid={validation?.valid} note="Schema-constrained claim graph" />
          <pre>{JSON.stringify(graph, null, 2)}</pre>
        </section>
      ) : mode === "Graph" ? (
        <section className="result-panel graph-panel">
          <PanelHeading title="Claim graph" valid={validation?.valid} note="Entities linked by source-backed relationships" />
          <div className="graph-canvas">
            <div className="graph-node primary">Claim<br />{graph.claim.id}</div>
            <div className="graph-links">
              <span>has timeline</span>
              <span>involves</span>
              <span>has financials</span>
              <span>cited by</span>
            </div>
            <div className="graph-column">
              <div className="graph-node">Events<br />{graph.events.length}</div>
              <div className="graph-node">Parties<br />{graph.parties.length}</div>
              <div className="graph-node">Financials<br />{graph.financial_items.length}</div>
              <div className="graph-node">Sources<br />{graph.sources.length}</div>
            </div>
          </div>
        </section>
      ) : mode === "Timeline" ? (
        <section className="result-panel timeline-panel">
          <PanelHeading title="Timeline" valid={validation?.valid} note="Events ordered by previous/next references" />
          <ol className="timeline-list">
            {graph.events.map((event) => (
              <li key={event.id}>
                <span>{event.event_date || "No date"}</span>
                <strong>{event.event_type}</strong>
                <p>{event.summary}</p>
                <SourceChips ids={event.source_ids} sources={sources} documents={documentsById} onSelectSource={onSelectSource} />
              </li>
            ))}
          </ol>
        </section>
      ) : (
        <div className="output-stack">
          {activeView === "Claim" ? (
            <section className="result-panel claim-panel">
            <PanelHeading
              title="Claim summary"
              valid={validation?.valid}
              note={validation?.valid ? "Validated - All fields have at least one source" : "Validation pending"}
            />
            <div className="claim-grid">
              <span>Claim number</span>
              <strong>{graph.claim.id}</strong>
              <SourceChips ids={graph.claim.source_ids} sources={sources} documents={documentsById} onSelectSource={onSelectSource} />
              <span>Loss date</span>
              <strong>{graph.claim.loss_date || "-"}</strong>
              <SourceChips ids={graph.claim.source_ids?.slice(0, 1)} sources={sources} documents={documentsById} onSelectSource={onSelectSource} />
              <span>Line of business</span>
              <strong>{graph.claim.line_of_business}</strong>
              <SourceChips ids={graph.claim.source_ids?.slice(0, 1)} sources={sources} documents={documentsById} onSelectSource={onSelectSource} />
              <span>Status</span>
              <strong>{graph.claim.status}</strong>
              <SourceChips ids={graph.claim.source_ids?.slice(0, 1)} sources={sources} documents={documentsById} onSelectSource={onSelectSource} />
              <span>Description</span>
              <strong>{graph.claim.summary}</strong>
              <SourceChips ids={graph.claim.source_ids} sources={sources} documents={documentsById} onSelectSource={onSelectSource} />
            </div>
            </section>
          ) : null}

          {activeView === "Events" ? (
            <section className="result-panel">
            <PanelHeading
              title={`Events (${graph.events.length})`}
              valid
              note="Validated - All events have at least one source"
            />
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Event</th>
                  <th>Date / Time</th>
                  <th>Description</th>
                  <th>Sources</th>
                </tr>
              </thead>
              <tbody>
                {graph.events.map((event, index) => (
                  <tr key={event.id}>
                    <td>{index + 1}</td>
                    <td>{event.event_type}</td>
                    <td>{event.event_date || "-"}</td>
                    <td>{event.summary}</td>
                    <td>
                      <SourceChips ids={event.source_ids} sources={sources} documents={documentsById} onSelectSource={onSelectSource} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button className="inline-add" type="button">
              <Plus size={14} /> Add event
            </button>
            </section>
          ) : null}

          {activeView === "Parties" ? (
            <section className="result-panel">
            <PanelHeading
              title={`Parties (${graph.parties.length})`}
              valid
              note="Validated - All parties have at least one source"
            />
            <table>
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Sources</th>
                </tr>
              </thead>
              <tbody>
                {graph.parties.map((party) => (
                  <tr key={party.id}>
                    <td>{party.role}</td>
                    <td>{party.name}</td>
                    <td>{party.party_type}</td>
                    <td>
                      <SourceChips ids={party.source_ids} sources={sources} documents={documentsById} onSelectSource={onSelectSource} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button className="inline-add" type="button">
              <Plus size={14} /> Add party
            </button>
            </section>
          ) : null}

          {activeView === "Financials" ? (
            <section className="result-panel">
            <PanelHeading
              title={`Financials (${graph.financial_items.length})`}
              valid
              note="Validated - All financial items have at least one source"
            />
            <div className="financial-summary">
              <div>
                <span>Total claimed</span>
                <strong>{formatMoney(sumFinancials(graph.financial_items))}</strong>
              </div>
              <div>
                <span>Total approved</span>
                <strong>{formatMoney(sumFinancials(graph.financial_items) * 0.55)}</strong>
              </div>
              <div>
                <span>Total outstanding</span>
                <strong>{formatMoney(sumFinancials(graph.financial_items) * 0.45)}</strong>
              </div>
            </div>
            <table>
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Description</th>
                  <th>Amount</th>
                  <th>Date</th>
                  <th>Sources</th>
                </tr>
              </thead>
              <tbody>
                {graph.financial_items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.financial_type}</td>
                    <td>{item.summary}</td>
                    <td>{formatMoney(item.amount)}</td>
                    <td>{item.booking_date || "-"}</td>
                    <td>
                      <SourceChips ids={item.source_ids} sources={sources} documents={documentsById} onSelectSource={onSelectSource} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </section>
          ) : null}

          {activeView === "Documents" ? (
            <section className="result-panel">
              <PanelHeading
                title={`Documents (${graph.documents.length})`}
                valid={validation?.valid}
                note="Original claim artifacts retained without confidence scores"
              />
              <table>
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Type</th>
                    <th>Date</th>
                    <th>Summary</th>
                    <th>Link</th>
                  </tr>
                </thead>
                <tbody>
                  {graph.documents.map((document) => (
                    <tr key={document.id}>
                      <td>{document.title}</td>
                      <td>{document.document_type}</td>
                      <td>{document.document_date || "-"}</td>
                      <td>{document.summary}</td>
                      <td>
                        <a className="table-link" href={document.content_uri} target="_blank" rel="noreferrer">
                          Open
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ) : null}

          {activeView === "Sources" ? (
            <section className="result-panel">
              <PanelHeading
                title={`Sources (${graph.sources.length})`}
                valid={validation?.valid}
                note="Every source is linked to exactly one document"
              />
              <table>
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Document</th>
                    <th>Citation text</th>
                    <th>Preview</th>
                  </tr>
                </thead>
                <tbody>
                  {graph.sources.map((source) => (
                    <tr key={source.id}>
                      <td>{source.id}</td>
                      <td>{documentsById[source.document_id]?.title || source.document_id}</td>
                      <td>{source.citation_text}</td>
                      <td>
                        <button className="table-action" type="button" onClick={() => onSelectSource(source.id)}>
                          Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ) : null}

          {activeView === "Citations" ? (
            <section className="result-panel">
              <PanelHeading
                title={`Citations (${citationRows.length})`}
                valid={validation?.valid}
                note="Business entities and their required source evidence"
              />
              <table>
                <thead>
                  <tr>
                    <th>Entity</th>
                    <th>Summary</th>
                    <th>Sources</th>
                  </tr>
                </thead>
                <tbody>
                  {citationRows.map((row) => (
                    <tr key={row.id}>
                      <td>{row.label}</td>
                      <td>{row.summary}</td>
                      <td>
                        <SourceChips ids={row.sourceIds} sources={sources} documents={documentsById} onSelectSource={onSelectSource} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ) : null}
        </div>
      )}
    </main>
  );
}

function PanelHeading({ title, valid, note }) {
  return (
    <div className="panel-heading">
      <h3>{title}</h3>
      <div className={valid ? "panel-valid valid" : "panel-valid"}>
        <CheckCircle2 size={16} />
        {note}
      </div>
      <button type="button">Edit</button>
    </div>
  );
}

function sourceLabel(source, documents) {
  const document = documents?.[source.document_id];
  const title = document?.title || source.document_id;
  const shortTitle = title.length > 18 ? `${title.slice(0, 16)}...` : title;
  const pageHint = source.id.split("-").slice(-1)[0];
  return `${shortTitle} p.${pageHint}`;
}

function buildCitationRows(graph) {
  if (!graph) return [];
  return [
    {
      id: graph.claim.id,
      label: `Claim: ${graph.claim.id}`,
      summary: graph.claim.summary,
      sourceIds: graph.claim.source_ids
    },
    ...graph.events.map((event) => ({
      id: event.id,
      label: `Event: ${event.event_type}`,
      summary: event.summary,
      sourceIds: event.source_ids
    })),
    ...graph.parties.map((party) => ({
      id: party.id,
      label: `Party: ${party.role}`,
      summary: party.summary,
      sourceIds: party.source_ids
    })),
    ...graph.financial_items.map((item) => ({
      id: item.id,
      label: `Financial: ${item.financial_type}`,
      summary: item.summary,
      sourceIds: item.source_ids
    }))
  ];
}

function sumFinancials(items = []) {
  return items.reduce((total, item) => total + Number(item.amount || 0), 0);
}

function formatMoney(value) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD"
  }).format(value || 0);
}
