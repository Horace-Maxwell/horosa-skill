export function unwrapResultEnvelope(value) {
  let current = value;
  for (let i = 0; i < 4; i += 1) {
    if (!current || typeof current !== 'object' || Array.isArray(current)) {
      return current;
    }
    if (current.Result && typeof current.Result === 'object') {
      current = current.Result;
      continue;
    }
    if (current.result && typeof current.result === 'object') {
      current = current.result;
      continue;
    }
    return current;
  }
  return current;
}

export function unwrapNamedObject(value, key) {
  const current = unwrapResultEnvelope(value);
  if (current && typeof current === 'object' && !Array.isArray(current) && current[key] && typeof current[key] === 'object') {
    return current[key];
  }
  return current;
}
