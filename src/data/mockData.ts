import type { Hackathon, AIDeal, UnverifiedSignal } from '../types';

export const MOCK_HACKATHONS: Hackathon[] = [
  {
    id: 'hack-001',
    title: 'Global AI Agents Developer Challenge 2026',
    organizer: 'Anthropic & Vercel',
    description: 'Build autonomous AI agents using Claude 4.5 Sonnet & Next.js App Router. Solve real-world developer workflows with deterministic tool calling and multi-agent coordination.',
    registrationOpenAt: '2026-07-01T00:00:00Z',
    registrationDeadline: '2026-08-10T23:59:59Z',
    submissionDeadline: '2026-08-25T23:59:59Z',
    mode: 'online',
    eligibleCountries: ['Worldwide'],
    eligibility: ['Developer', 'Student', 'Startup'],
    teamMin: 1,
    teamMax: 4,
    prizeValue: 50000,
    prizeCurrency: 'USD',
    technologies: ['AI', 'LLM', 'Next.js', 'Python', 'TypeScript'],
    officialUrl: 'https://anthropic.com/hackathon-2026',
    discoverySources: [
      {
        type: 'official_site',
        url: 'https://anthropic.com/hackathon-2026',
        fetchedAt: '2026-07-23T18:30:00Z',
        tier: 'Tier 1 (Official)'
      },
      {
        type: 'devpost',
        url: 'https://devpost.com/hackathons/global-ai-agents-2026',
        fetchedAt: '2026-07-23T14:10:00Z',
        tier: 'Tier 2 (Aggregator)'
      },
      {
        type: 'x',
        url: 'https://x.com/anthropic/status/18920192830',
        author: '@AnthropicAI',
        postId: '18920192830',
        fetchedAt: '2026-07-23T10:00:00Z',
        tier: 'Tier 3 (Discovery Signal)'
      }
    ],
    verificationStatus: 'verified_active',
    confidenceScore: 0.98,
    lastCheckedAt: '2026-07-23T21:45:00Z',
    suitableReasons: [
      'Fully online & open worldwide',
      'Individual participation allowed (1-4 members)',
      'High prize pool ($50,000 USD total)',
      'Registration closes in 18 days',
      'Free Anthropic Claude credits provided on registration'
    ],
    effortEstimate: '1-2 Weeks',
    audit: {
      lastCheckedAt: '2026-07-23T21:45:00Z',
      confidenceScore: 0.98,
      scoreBreakdown: {
        statusAndDeadline: 35,
        keywordMatch: 25,
        sourceCredibility: 20,
        freshness: 14,
        completeness: 4
      },
      verifierNotes: 'Verified against Tier 1 official terms and Devpost aggregator. Deadlines matched cleanly across official blog post and rules page.',
      checkedUrls: [
        'https://anthropic.com/hackathon-2026',
        'https://devpost.com/hackathons/global-ai-agents-2026'
      ],
      pipelineStep: 'verified'
    },
    bookmarked: true,
    alertEnabled: true
  },
  {
    id: 'hack-002',
    title: 'Open Source AI Infra Hackathon',
    organizer: 'Hugging Face & Modal Labs',
    description: 'Deploy fine-tuned open-weight models, vLLM acceleration pipelines, and serverless GPU clusters. Focus on latency reduction, quantization, and local execution.',
    registrationOpenAt: '2026-07-10T00:00:00Z',
    registrationDeadline: '2026-08-02T23:59:59Z',
    submissionDeadline: '2026-08-08T23:59:59Z',
    mode: 'online',
    eligibleCountries: ['Worldwide'],
    eligibility: ['Developer', 'Open Source Contributor'],
    teamMin: 1,
    teamMax: 3,
    prizeValue: 25000,
    prizeCurrency: 'USD',
    technologies: ['PyTorch', 'vLLM', 'CUDA', 'Python', 'Docker'],
    officialUrl: 'https://huggingface.co/events/infra-hack-2026',
    discoverySources: [
      {
        type: 'official_site',
        url: 'https://huggingface.co/events/infra-hack-2026',
        fetchedAt: '2026-07-23T19:00:00Z',
        tier: 'Tier 1 (Official)'
      },
      {
        type: 'x',
        url: 'https://x.com/huggingface/status/18933211029',
        author: '@huggingface',
        postId: '18933211029',
        fetchedAt: '2026-07-22T08:12:00Z',
        tier: 'Tier 3 (Discovery Signal)'
      }
    ],
    verificationStatus: 'verified_active',
    confidenceScore: 0.94,
    lastCheckedAt: '2026-07-23T20:15:00Z',
    suitableReasons: [
      'Fully online & worldwide eligible',
      'Free GPU compute credits ($200 Modal credits/team)',
      'Focus on PyTorch & open-source tools',
      'Registration closes in 10 days'
    ],
    effortEstimate: '1 Week',
    audit: {
      lastCheckedAt: '2026-07-23T20:15:00Z',
      confidenceScore: 0.94,
      scoreBreakdown: {
        statusAndDeadline: 34,
        keywordMatch: 24,
        sourceCredibility: 19,
        freshness: 12,
        completeness: 5
      },
      verifierNotes: 'Verified via Hugging Face official event directory. Registration link leads to Modal Labs sign-up page with valid SSL and active dates.',
      checkedUrls: [
        'https://huggingface.co/events/infra-hack-2026'
      ],
      pipelineStep: 'verified'
    }
  },
  {
    id: 'hack-003',
    title: 'Student Innovation Championship 2026',
    organizer: 'GitHub & Major League Hacking (MLH)',
    description: 'Global hackathon designed exclusively for high school, undergraduate, and graduate students. Build impactful software using GitHub Copilot and Actions.',
    registrationOpenAt: '2026-06-15T00:00:00Z',
    registrationDeadline: '2026-07-31T23:59:59Z',
    submissionDeadline: '2026-08-05T23:59:59Z',
    mode: 'online',
    eligibleCountries: ['Worldwide'],
    eligibility: ['Student'],
    teamMin: 1,
    teamMax: 4,
    prizeValue: 15000,
    prizeCurrency: 'USD',
    technologies: ['Web', 'GitHub Actions', 'Copilot API', 'React'],
    officialUrl: 'https://mlh.io/seasons/2026/events/student-innovation',
    discoverySources: [
      {
        type: 'mlh',
        url: 'https://mlh.io/seasons/2026/events/student-innovation',
        fetchedAt: '2026-07-23T12:00:00Z',
        tier: 'Tier 2 (Aggregator)'
      }
    ],
    verificationStatus: 'verified_active',
    confidenceScore: 0.96,
    lastCheckedAt: '2026-07-23T21:00:00Z',
    suitableReasons: [
      'Dedicated Student category',
      'Free GitHub Student Developer Pack bonus',
      'Closes registration in 8 days'
    ],
    effortEstimate: '1-2 Days',
    audit: {
      lastCheckedAt: '2026-07-23T21:00:00Z',
      confidenceScore: 0.96,
      scoreBreakdown: {
        statusAndDeadline: 35,
        keywordMatch: 24,
        sourceCredibility: 18,
        freshness: 14,
        completeness: 5
      },
      verifierNotes: 'Verified MLH official calendar event.',
      checkedUrls: ['https://mlh.io/seasons/2026/events/student-innovation'],
      pipelineStep: 'verified'
    }
  },
  {
    id: 'hack-004',
    title: 'Autonomous Code Refactoring Challenge',
    organizer: 'JetBrains & Cursor AI',
    description: 'Build IDE plugins or CLI bots that auto-refactor legacy PHP/MySQLi codebase to modern clean architecture using AST analysis and LLMs.',
    registrationOpenAt: '2026-07-01T00:00:00Z',
    registrationDeadline: '2026-08-15T23:59:59Z',
    submissionDeadline: '2026-09-01T23:59:59Z',
    mode: 'online',
    eligibleCountries: ['Worldwide'],
    eligibility: ['Developer', 'Student'],
    teamMin: 1,
    teamMax: 2,
    prizeValue: 30000,
    prizeCurrency: 'USD',
    technologies: ['TypeScript', 'AST', 'PHP', 'LLM', 'IDE Extension'],
    officialUrl: 'https://jetbrains.com/challenge/code-refactor-2026',
    discoverySources: [
      {
        type: 'official_site',
        url: 'https://jetbrains.com/challenge/code-refactor-2026',
        fetchedAt: '2026-07-21T10:00:00Z',
        tier: 'Tier 1 (Official)'
      }
    ],
    verificationStatus: 'likely_active',
    confidenceScore: 0.88,
    lastCheckedAt: '2026-07-22T14:30:00Z',
    suitableReasons: [
      'Great match for refactoring & developer tools',
      '1-2 person small team format',
      'Generous 6-week window'
    ],
    effortEstimate: '2-3 Weeks',
    audit: {
      lastCheckedAt: '2026-07-22T14:30:00Z',
      confidenceScore: 0.88,
      scoreBreakdown: {
        statusAndDeadline: 32,
        keywordMatch: 23,
        sourceCredibility: 18,
        freshness: 11,
        completeness: 4
      },
      verifierNotes: 'Official post verified, pending secondary aggregator cross-reference.',
      checkedUrls: ['https://jetbrains.com/challenge/code-refactor-2026'],
      pipelineStep: 'verified'
    }
  }
];

export const MOCK_AI_DEALS: AIDeal[] = [
  {
    id: 'deal-001',
    productName: 'Claude 4.5 Sonnet Developer Credits',
    provider: 'Anthropic',
    offerType: 'free_credits',
    offerValue: '$100 Free Credits',
    targetUsers: ['New Developers', 'Hackathon Participants'],
    requirements: ['Verified Developer Account', 'No Credit Card required for first $25'],
    startsAt: '2026-07-01T00:00:00Z',
    expiresAt: '2026-08-31T23:59:59Z',
    supportedRegions: ['Worldwide'],
    officialTermsUrl: 'https://console.anthropic.com/settings/credits',
    claimUrl: 'https://console.anthropic.com/claim?code=DEVRADAR2026',
    verificationStatus: 'verified_active',
    confidenceScore: 0.97,
    lastCheckedAt: '2026-07-23T21:30:00Z',
    description: 'Get $100 in free Claude API credits valid for Prompt Caching, Thinking Mode, and Vision endpoints. Perfect for testing AI agent loops.',
    tags: ['AI', 'LLM', 'API Credits', 'Anthropic'],
    discoverySources: [
      {
        type: 'official_site',
        url: 'https://console.anthropic.com/settings/credits',
        fetchedAt: '2026-07-23T18:00:00Z',
        tier: 'Tier 1 (Official)'
      },
      {
        type: 'x',
        url: 'https://x.com/AnthropicAI/status/18944109283',
        author: '@AnthropicAI',
        postId: '18944109283',
        fetchedAt: '2026-07-23T09:00:00Z',
        tier: 'Tier 3 (Discovery Signal)'
      }
    ],
    suitableReasons: [
      'Verified working promo link',
      'No credit card required upfront',
      'Works with Python & Node SDKs',
      'Active until end of August'
    ],
    audit: {
      lastCheckedAt: '2026-07-23T21:30:00Z',
      confidenceScore: 0.97,
      scoreBreakdown: {
        statusAndDeadline: 35,
        keywordMatch: 25,
        sourceCredibility: 20,
        freshness: 13,
        completeness: 4
      },
      verifierNotes: 'HTTP 200 on terms page. Promo code endpoint validated dynamically via HTTP HEAD headers.',
      checkedUrls: ['https://console.anthropic.com/settings/credits'],
      pipelineStep: 'verified'
    },
    bookmarked: true,
    alertEnabled: true
  },
  {
    id: 'deal-002',
    productName: 'Vercel AI SDK & Compute Free Tier',
    provider: 'Vercel',
    offerType: 'free_tier',
    offerValue: 'Permanent Free Tier + 1M Tokens/mo',
    targetUsers: ['Next.js Developers', 'Frontend Engineers'],
    requirements: ['GitHub Sign In'],
    startsAt: '2026-01-01T00:00:00Z',
    expiresAt: null,
    supportedRegions: ['Worldwide'],
    officialTermsUrl: 'https://vercel.com/pricing',
    claimUrl: 'https://vercel.com/signup',
    verificationStatus: 'verified_active',
    confidenceScore: 0.99,
    lastCheckedAt: '2026-07-23T22:00:00Z',
    description: 'Deploy Next.js apps with streaming AI responses, Edge functions, KV storage, and 1 Million free tokens/month via Vercel AI Gateway.',
    tags: ['Hosting', 'Next.js', 'Free Tier', 'Vercel'],
    discoverySources: [
      {
        type: 'official_site',
        url: 'https://vercel.com/pricing',
        fetchedAt: '2026-07-23T22:00:00Z',
        tier: 'Tier 1 (Official)'
      }
    ],
    suitableReasons: [
      'Permanent Free Tier (No expiration)',
      'Zero-config Next.js deployment',
      'Built-in AI Gateway integration'
    ],
    audit: {
      lastCheckedAt: '2026-07-23T22:00:00Z',
      confidenceScore: 0.99,
      scoreBreakdown: {
        statusAndDeadline: 35,
        keywordMatch: 25,
        sourceCredibility: 20,
        freshness: 14,
        completeness: 5
      },
      verifierNotes: 'Official pricing table verified. Free tier limits confirmed active.',
      checkedUrls: ['https://vercel.com/pricing'],
      pipelineStep: 'verified'
    }
  },
  {
    id: 'deal-003',
    productName: 'GitHub Student Developer Pack (AI Edition)',
    provider: 'GitHub & Partners',
    offerType: 'student_program',
    offerValue: 'Free Copilot Pro + $200 Azure AI Credits',
    targetUsers: ['High School & University Students'],
    requirements: ['School Email / Student ID ID proof'],
    startsAt: '2026-01-01T00:00:00Z',
    expiresAt: '2026-12-31T23:59:59Z',
    supportedRegions: ['Worldwide'],
    officialTermsUrl: 'https://education.github.com/pack',
    claimUrl: 'https://education.github.com/pack',
    verificationStatus: 'verified_active',
    confidenceScore: 0.99,
    lastCheckedAt: '2026-07-23T20:00:00Z',
    description: 'Includes free GitHub Copilot Pro access, $200 in Azure AI Services credits, free domain names, and 20+ premium dev tools.',
    tags: ['Student', 'Copilot', 'Azure', 'GitHub'],
    discoverySources: [
      {
        type: 'official_site',
        url: 'https://education.github.com/pack',
        fetchedAt: '2026-07-23T20:00:00Z',
        tier: 'Tier 1 (Official)'
      }
    ],
    suitableReasons: [
      '100% Free for verified students',
      'Includes full Copilot Pro access',
      'Annual renewable student status'
    ],
    audit: {
      lastCheckedAt: '2026-07-23T20:00:00Z',
      confidenceScore: 0.99,
      scoreBreakdown: {
        statusAndDeadline: 35,
        keywordMatch: 25,
        sourceCredibility: 20,
        freshness: 14,
        completeness: 5
      },
      verifierNotes: 'Verified official GitHub Education pack URL.',
      checkedUrls: ['https://education.github.com/pack'],
      pipelineStep: 'verified'
    }
  },
  {
    id: 'deal-004',
    productName: 'DeepSeek-V4-Flash API Pricing',
    provider: 'DeepSeek AI',
    offerType: 'free_model',
    offerValue: '$0.28 per 1M Output Tokens',
    targetUsers: ['All Developers'],
    requirements: ['API Key'],
    startsAt: '2026-07-15T00:00:00Z',
    expiresAt: null,
    supportedRegions: ['Worldwide'],
    officialTermsUrl: 'https://platform.deepseek.com/api-docs/pricing',
    claimUrl: 'https://platform.deepseek.com',
    verificationStatus: 'verified_active',
    confidenceScore: 0.95,
    lastCheckedAt: '2026-07-23T19:20:00Z',
    description: 'Pricing update! DeepSeek-V4-Flash model now offers industry-lowest API pricing at $0.0028 per 1M input tokens (cache hit) and $0.28 per 1M output tokens.',
    tags: ['DeepSeek-V4', 'Reasoning Model', 'Flash', 'Open Weights'],
    discoverySources: [
      {
        type: 'official_site',
        url: 'https://platform.deepseek.com/api-docs/pricing',
        fetchedAt: '2026-07-23T19:20:00Z',
        tier: 'Tier 1 (Official)'
      },
      {
        type: 'x',
        url: 'https://x.com/deepseek_ai/status/1895019284',
        author: '@deepseek_ai',
        postId: '1895019284',
        fetchedAt: '2026-07-23T11:00:00Z',
        tier: 'Tier 3 (Discovery Signal)'
      }
    ],
    suitableReasons: [
      'Ultra cheap reasoning API',
      'Free 500k initial trial tokens',
      'OpenAI API format compatible'
    ],
    audit: {
      lastCheckedAt: '2026-07-23T19:20:00Z',
      confidenceScore: 0.95,
      scoreBreakdown: {
        statusAndDeadline: 34,
        keywordMatch: 24,
        sourceCredibility: 19,
        freshness: 13,
        completeness: 5
      },
      verifierNotes: 'Verified pricing table update on official site.',
      checkedUrls: ['https://platform.deepseek.com/api-docs/pricing'],
      pipelineStep: 'verified'
    }
  }
];

export const MOCK_UNVERIFIED_SIGNALS: UnverifiedSignal[] = [
  {
    id: 'sig-101',
    sourceType: 'x_post',
    postId: '18977200192',
    author: '@tech_builder_xyz',
    rawText: 'Just launched the Web3 AI Hackathon! $10,000 in prizes for best Solana + Claude integration! Register here: https://solana-ai-hack.dev #hackathon #solana #ai',
    createdAt: '2026-07-23T20:12:00Z',
    discoveredUrls: ['https://solana-ai-hack.dev'],
    candidateType: 'hackathon',
    extractedInfo: {
      title: 'Solana AI Hackathon 2026',
      organizer: 'Solana Ecosystem Labs',
      prizeValue: 10000,
      prizeCurrency: 'USD',
      mode: 'online',
      technologies: ['Solana', 'AI', 'Rust', 'TypeScript']
    },
    verificationStatus: 'needs_review',
    confidenceScore: 0.52
  },
  {
    id: 'sig-102',
    sourceType: 'x_post',
    postId: '18978110931',
    author: '@ai_promos_daily',
    rawText: 'Get $500 free credits on Mistral AI API for new startup accounts! Use code MISTRALSTART2026 at checkout https://console.mistral.ai/offers',
    createdAt: '2026-07-23T18:45:00Z',
    discoveredUrls: ['https://console.mistral.ai/offers'],
    candidateType: 'ai_deal',
    extractedInfo: {
      productName: 'Mistral AI Startup Credits',
      provider: 'Mistral AI',
      offerValue: '$500 Credits',
      offerType: 'free_credits'
    },
    verificationStatus: 'needs_review',
    confidenceScore: 0.64
  }
];
