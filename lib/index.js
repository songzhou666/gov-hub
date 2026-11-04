/**
 * gov-hub DSH bundle: registers the gov-hub skill as a bundled skill provider.
 *
 * Plain ESM, zero dependencies, no build step. The skill body is the repo-root
 * SKILL.md (frontmatter stripped); references/ ship next to it as resources.
 */

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const PROVIDER_NAME = 'gov-hub-bundle'
const SKILL_URL = new URL('../SKILL.md', import.meta.url)
const RESOURCE_BASE = {
  kind: 'directory',
  path: fileURLToPath(new URL('../', import.meta.url)),
}

const RAW = readFileSync(SKILL_URL, 'utf8')

/** Strip YAML frontmatter; return { attrs, body }. */
function split(raw) {
  const m = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(raw)
  if (!m) return { attrs: {}, body: raw }
  const attrs = {}
  for (const line of m[1].split(/\r?\n/)) {
    const kv = /^(\w[\w-]*):\s*(.+)$/.exec(line.trim())
    if (kv && !(kv[1] in attrs)) attrs[kv[1]] = kv[2].trim().replace(/^['"]|['"]$/g, '')
  }
  return { attrs, body: m[2] }
}

const { attrs, body } = split(RAW)
const NAME = attrs.name || 'gov-hub'
const DESCRIPTION = attrs.description || ''
const WHEN_TO_USE = attrs.whenToUse

const INVOCATION = { modelInvocable: true, userInvocable: true }
const RANK = 600 // BUNDLED_SKILL_RANK, inlined to keep zero dependencies

const candidate = {
  name: NAME,
  description: DESCRIPTION,
  ...(WHEN_TO_USE ? { whenToUse: WHEN_TO_USE } : {}),
  invocation: INVOCATION,
  provider: PROVIDER_NAME,
  source: 'bundled',
  resourceBase: RESOURCE_BASE,
  rank: RANK,
  locator: SKILL_URL,
}

const provider = {
  name: PROVIDER_NAME,
  list: () => Promise.resolve([candidate]),
  async get() {
    return {
      name: NAME,
      description: DESCRIPTION,
      ...(WHEN_TO_USE ? { whenToUse: WHEN_TO_USE } : {}),
      invocation: INVOCATION,
      provider: PROVIDER_NAME,
      source: 'bundled',
      resourceBase: RESOURCE_BASE,
      content: body,
    }
  },
}

export const name = 'gov-hub-bundle'
export const inject = ['skills']
export function apply(ctx) {
  ctx.skills.registerProvider(() => provider)
}
