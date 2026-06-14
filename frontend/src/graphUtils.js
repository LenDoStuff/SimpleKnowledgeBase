export function groupDocuments(documents) {
  return documents.reduce((groups, document) => {
    const group = document.sort_group || "Other";
    groups[group] = groups[group] || [];
    groups[group].push(document);
    return groups;
  }, {});
}

export function sourceLookup(graph) {
  const sources = graph?.sources || [];
  return sources.reduce((lookup, source) => {
    lookup[source.id] = source;
    return lookup;
  }, {});
}
