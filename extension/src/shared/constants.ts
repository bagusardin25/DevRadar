export const DEFAULT_API_BASE_URL = 'http://localhost:8000';

export const TECH_KEYWORDS = [
  'Python', 'TypeScript', 'JavaScript', 'Rust', 'Go', 'Solidity',
  'AI', 'LLM', 'GPT', 'Claude', 'Gemini',
  'Next.js', 'React', 'Vue', 'Angular', 'Svelte',
  'Node.js', 'Deno', 'Bun',
  'CUDA', 'PyTorch', 'TensorFlow', 'JAX',
  'Web3', 'Blockchain', 'Ethereum', 'Solana',
  'Docker', 'Kubernetes', 'AWS', 'GCP', 'Azure',
  'PostgreSQL', 'MongoDB', 'Redis',
  'GraphQL', 'REST', 'gRPC',
  'Flutter', 'Swift', 'Kotlin',
  'Anthropic', 'OpenAI', 'Hugging Face',
];

export const KNOWN_PLATFORMS: Record<string, string> = {
  'devpost.com': 'Devpost',
  'mlh.io': 'MLH',
  'dorahacks.io': 'DoraHacks',
  'gitcoin.co': 'Gitcoin',
  'hackerearth.com': 'HackerEarth',
  'hackathon.com': 'Hackathon.com',
  'luma.com': 'Luma',
  'eventbrite.com': 'Eventbrite',
  'unstop.com': 'Unstop',
  'taikai.network': 'Taikai',
};

export const ISO_DATE_RE =
  /\b(20\d{2}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?)\b/g;

export const US_DATE_RE =
  /\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+20\d{2})\b/gi;

export const MONEY_RE =
  /(?:\$|USD\s*|€|EUR\s*|£|GBP\s*)([\d,]+(?:\.\d{1,2})?)\s*(k|K|M|m|USD|EUR|GBP)?/g;

export const PRIZE_RE =
  /(?:prize|pool|award|bounty|reward)[^\n$€£]{0,40}(?:\$|USD\s*)([\d,]+(?:\.\d+)?)\s*(k|K|M|m|USD|usd)?/i;

export const CREDITS_RE =
  /(?:\$|USD\s*)([\d,]+(?:\.\d+)?)\s*(?:USD\s+)?(?:in\s+)?(?:free\s+)?credits/i;

export const TEAM_RE = /teams?\s+of\s+(\d+)\s*[-–to]+\s*(\d+)/i;
export const TEAM_SINGLE_RE = /(?:team\s+size|up to)\s+(\d+)/i;

export const HACKATHON_SIGNALS = [
  /\bhackathon\b/i, /\bhack\b/i, /\bchallenge\b/i, /\bcompetition\b/i,
  /\bbounty\b/i, /\bbuildathon\b/i, /\bsubmission\s+deadline\b/i,
  /\bprize\s+pool\b/i, /\bjudging\b/i, /\bdevpost\b/i,
];

export const AI_OFFER_SIGNALS = [
  /\bfree\s+credits?\b/i, /\bfree\s+tier\b/i, /\btrial\b/i,
  /\bAPI\s+key\b/i, /\bpricing\b/i, /\bfree\s+model\b/i,
  /\bopen\s+weights?\b/i, /\bstudent\s+program\b/i,
  /\bdeveloper\s+program\b/i, /\bcredits?\s+program\b/i,
];

export const MODE_PATTERNS: Array<[RegExp, string]> = [
  [/\b(?:fully\s+)?online\b|\bvirtual\b|\bremote\b/i, 'online'],
  [/\bhybrid\b/i, 'hybrid'],
  [/\bin[-\s]?person\b|\bon[-\s]?site\b/i, 'in_person'],
];

export const OFFER_TYPE_PATTERNS: Array<[RegExp, string]> = [
  [/free\s+tier|always\s+free/i, 'free_tier'],
  [/free\s+credits|developer\s+credits/i, 'free_credits'],
  [/student\s+program|github\s+student/i, 'student_program'],
  [/open\s*source\s+program/i, 'open_source_program'],
  [/hackathon\s+credits/i, 'hackathon_credits'],
  [/promo\s*code|coupon/i, 'promo_code'],
  [/free\s+model|open\s+weights/i, 'free_model'],
  [/self[-\s]?hosted/i, 'self_hosted_weights'],
  [/\btrial\b/i, 'trial'],
];

export const REGISTRATION_LINK_KEYWORDS = [
  'register', 'apply', 'submit', 'signup', 'sign-up', 'sign_up',
  'join', 'enroll', 'participate', 'claim', 'start',
];
