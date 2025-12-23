export type SSEEvent = {
  event: string
  data: string
}

function parseEventBlock(block: string): SSEEvent | null {
  const lines = block.split('\n')
  let event = 'message'
  const dataLines: string[] = []

  for (const rawLine of lines) {
    const line = rawLine.replace(/\r$/, '')
    if (!line) continue
    if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim()
      continue
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart())
      continue
    }
  }

  if (dataLines.length === 0) return null
  return { event, data: dataLines.join('\n') }
}

export async function fetchSSE(
  url: string,
  init: RequestInit,
  onEvent: (evt: SSEEvent) => void,
): Promise<void> {
  const resp = await fetch(url, init)
  if (!resp.ok) {
    const text = await resp.text().catch(() => '')
    throw new Error(`SSE request failed: ${resp.status} ${text}`)
  }
  if (!resp.body) throw new Error('SSE response has no body')

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')

  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let idx = buffer.indexOf('\n\n')
    while (idx !== -1) {
      const block = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      const evt = parseEventBlock(block)
      if (evt) onEvent(evt)
      idx = buffer.indexOf('\n\n')
    }
  }
}

