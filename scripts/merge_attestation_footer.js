// Preserve the latest signed proof when a later run updates the shared PR comment unsigned.
const HEADING = '### 🔏 Signed attestation';
const UNSIGNED_NOTE = /^This run was not signed \(see notice\); the attestation above belongs to run .*\n?/gm;

function mergeUnsignedAttestation(body, previousBody) {
  if (!previousBody || body.includes(HEADING)) return body;
  const start = previousBody.indexOf(HEADING);
  if (start === -1) return body;
  const end = previousBody.indexOf('\n---\n', start);
  const block = previousBody.slice(start, end === -1 ? undefined : end + 1);
  const run = block.match(/^- \*\*Workflow run:\*\* \[[^\]]*\]\((https:\/\/[^)]+)\)/m);
  if (!run) return body;
  const signedBlock = block.replace(UNSIGNED_NOTE, '');
  const note = `This run was not signed (see notice); the attestation above belongs to run ${run[1]}\n`;
  const separator = '\n---\n';
  const insertion = body.lastIndexOf(separator);
  if (insertion === -1) return `${body.trimEnd()}\n\n${signedBlock}${note}`;
  return body.slice(0, insertion) + '\n' + signedBlock + note + body.slice(insertion);
}

module.exports = { mergeUnsignedAttestation };
