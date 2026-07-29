import { useState } from 'react';
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  Bookmark,
  Bell,
  Search,
  ShieldCheck,
  Globe,
  Download,
  Upload,
  Share2,
  Trash2,
  HelpCircle,
  Zap,
  Radar,
  GitCompareArrows,
} from 'lucide-react';

interface FaqItem {
  question: string;
  answer: string;
  icon: React.ReactNode;
  category: string;
}

const FAQ_ITEMS: FaqItem[] = [
  {
    category: 'Bookmarks',
    icon: <Bookmark className="w-4 h-4 text-[#FF5A36]" />,
    question: 'Why did my bookmarks disappear after clearing browser cache?',
    answer:
      'DevRadar stores bookmarks in your browser\'s localStorage — no account or server login is needed, but this also means clearing your browser cache / site data removes them. To protect your bookmarks, use the Export feature in the bookmarks drawer to save a JSON backup before clearing cache. You can re-import them anytime.',
  },
  {
    category: 'Bookmarks',
    icon: <Download className="w-4 h-4 text-[#FF5A36]" />,
    question: 'How do I back up my bookmarks?',
    answer:
      'Open the bookmarks drawer (bookmark icon in the top bar), then click "Export". This downloads a JSON file containing all your saved listing IDs. Keep this file safe — you can re-import it later on any browser.',
  },
  {
    category: 'Bookmarks',
    icon: <Upload className="w-4 h-4 text-[#FF5A36]" />,
    question: 'How do I import bookmarks from another browser or device?',
    answer:
      'Open the bookmarks drawer and click "Import". Select the JSON file you previously exported. You can choose to merge with your existing bookmarks or replace them entirely.',
  },
  {
    category: 'Bookmarks',
    icon: <Share2 className="w-4 h-4 text-[#7C3AED]" />,
    question: 'Can I share my bookmarks with someone?',
    answer:
      'Yes! In the bookmarks drawer, click the share button to generate a URL containing your bookmarked listing IDs. Anyone who opens that link will see your curated selection. They can then choose to save those items to their own local bookmarks.',
  },
  {
    category: 'Search & Filters',
    icon: <Search className="w-4 h-4 text-[#2563EB]" />,
    question: 'What is the difference between indexed search and live discovery?',
    answer:
      'Indexed search filters the listings already in the DevRadar catalogue — it is instant. Live discovery triggers a real-time scan of configured sources (websites, APIs) to find new listings that are not yet in the catalogue. Live discovery takes longer but can surface opportunities that were just posted.',
  },
  {
    category: 'Search & Filters',
    icon: <Radar className="w-4 h-4 text-[#FF5A36]" />,
    question: 'What does "Closing Soon" mean?',
    answer:
      'The "Closing Soon" filter shows hackathons whose registration deadline is within the next 14 days. This helps you catch opportunities before they close.',
  },
  {
    category: 'Search & Filters',
    icon: <Zap className="w-4 h-4 text-[#7C3AED]" />,
    question: 'What does "Free — No Card" mean for AI deals?',
    answer:
      'This filter shows AI offers that do not require a credit card to claim. It checks the listing\'s requirements field and hides offers that mention "credit card".',
  },
  {
    category: 'Verification',
    icon: <ShieldCheck className="w-4 h-4 text-[#059669]" />,
    question: 'What do the verification badges mean?',
    answer:
      'Each listing has a verification status: "Verified Active" means an operator confirmed it is live and accurate. "Likely Active" means it passed automated checks but has not been manually reviewed. "Needs Review" means it was recently discovered and is awaiting verification. "Registration Closed", "Expired", and "Cancelled" indicate listings that are no longer active.',
  },
  {
    category: 'Verification',
    icon: <ShieldCheck className="w-4 h-4 text-[#D97706]" />,
    question: 'How accurate are the listings?',
    answer:
      'Listings are sourced from official sites, aggregators, and discovery signals, then scored by an automated pipeline. Operators manually verify high-priority items. However, details can change at any time — always confirm on the official page before registering or paying.',
  },
  {
    category: 'Features',
    icon: <GitCompareArrows className="w-4 h-4 text-[#7C3AED]" />,
    question: 'How do I compare hackathons side by side?',
    answer:
      'On the Radar tab, each hackathon card has a "Compare" button. Select up to 3 hackathons, then click "Open Side-by-Side Table" in the floating bar at the bottom to see them compared across key fields like prize, deadline, mode, and technologies.',
  },
  {
    category: 'Features',
    icon: <Bell className="w-4 h-4 text-[#7C3AED]" />,
    question: 'How do email alerts work?',
    answer:
      'Click the bell icon in the top bar to subscribe to email alerts. You can filter by category (hackathons, AI deals, or both), technology, mode, and more. When new listings matching your criteria are published, you\'ll receive an email. You\'ll get a confirmation email first — click the link in it to activate your subscription.',
  },
  {
    category: 'Features',
    icon: <Globe className="w-4 h-4 text-[#FF5A36]" />,
    question: 'What is the browser extension?',
    answer:
      'The DevRadar browser extension detects hackathon and AI offer pages as you browse the web and shows a sidebar with relevant details. Click the globe icon in the top bar to preview how it works. The extension is available for Chrome and Firefox.',
  },
  {
    category: 'Data & Privacy',
    icon: <Trash2 className="w-4 h-4 text-[#DC2626]" />,
    question: 'What data does DevRadar store about me?',
    answer:
      'DevRadar does not require any login or account. Your bookmarks, alert preferences, theme, and layout settings are stored in your browser\'s localStorage only. Email alert subscriptions store your email on the server, but nothing else. No tracking cookies are used.',
  },
  {
    category: 'Data & Privacy',
    icon: <HelpCircle className="w-4 h-4 text-[#6B7280]" />,
    question: 'Is DevRadar affiliated with the listed hackathons or vendors?',
    answer:
      'No. DevRadar is an independent, open-source index. It is not affiliated with any organiser or vendor. Listings are community or operator-verified and can go stale — always confirm details on the official page.',
  },
];

const CATEGORIES = [...new Set(FAQ_ITEMS.map((item) => item.category))];

export function GuidePage() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  const filtered = activeCategory
    ? FAQ_ITEMS.filter((item) => item.category === activeCategory)
    : FAQ_ITEMS;

  return (
    <div className="max-w-4xl mx-auto px-4 lg:px-8 pt-8 pb-16">
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-white dark:bg-[#131A29] border-[1.5px] border-[#1C1B18] shadow-[3px_3px_0_0_#1C1B18] dark:shadow-[3px_3px_0_0_#D6DCE5] mb-4">
          <BookOpen className="w-7 h-7 text-[#FF5A36]" />
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#1C1B18] dark:text-white">
          User Guide
        </h1>
        <p className="mt-2 text-sm font-bold text-[#736F66] dark:text-[#94A3B8] max-w-lg mx-auto">
          Everything you need to know about using DevRadar — from bookmarks and search to verification and alerts.
        </p>
      </div>

      {/* Quick tips banner */}
      <div className="sharetopus-card p-5 rounded-2xl border-[1.5px] border-[#059669] bg-[#059669]/5 dark:bg-[#059669]/10 mb-8">
        <h2 className="text-sm font-extrabold text-[#059669] dark:text-[#34D399] mb-3 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4" />
          Quick Tips
        </h2>
        <ul className="space-y-2 text-xs font-bold text-[#1C1B18] dark:text-[#F8FAF9]">
          <li className="flex items-start gap-2">
            <span className="text-[#059669] shrink-0 mt-0.5">1.</span>
            <span><strong className="text-[#FF5A36]">Export your bookmarks</strong> regularly — they live in your browser and clearing cache removes them.</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-[#059669] shrink-0 mt-0.5">2.</span>
            <span><strong className="text-[#7C3AED]">Set up email alerts</strong> to get notified when new opportunities matching your interests appear.</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="text-[#059669] shrink-0 mt-0.5">3.</span>
            <span><strong className="text-[#2563EB]">Always verify on the official page</strong> before registering — listings can go stale.</span>
          </li>
        </ul>
      </div>

      {/* Category filter pills */}
      <div className="flex flex-wrap gap-2 mb-6">
        <button
          type="button"
          onClick={() => setActiveCategory(null)}
          className={`px-3 py-1.5 rounded-full text-xs font-extrabold transition-all border-[1.5px] ${
            activeCategory === null
              ? 'bg-[#1C1B18] dark:bg-white text-white dark:text-[#1C1B18] border-[#1C1B18] dark:border-white'
              : 'bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-[#D6DCE5] border-[#D6D5CF] dark:border-slate-700 hover:border-[#1C1B18] dark:hover:border-white'
          }`}
        >
          All
        </button>
        {CATEGORIES.map((cat) => (
          <button
            key={cat}
            type="button"
            onClick={() => setActiveCategory(cat === activeCategory ? null : cat)}
            className={`px-3 py-1.5 rounded-full text-xs font-extrabold transition-all border-[1.5px] ${
              activeCategory === cat
                ? 'bg-[#1C1B18] dark:bg-white text-white dark:text-[#1C1B18] border-[#1C1B18] dark:border-white'
                : 'bg-white dark:bg-[#131A29] text-[#1C1B18] dark:text-[#D6DCE5] border-[#D6D5CF] dark:border-slate-700 hover:border-[#1C1B18] dark:hover:border-white'
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* FAQ accordion */}
      <div className="space-y-3">
        {filtered.map((item) => {
          const globalIdx = FAQ_ITEMS.indexOf(item);
          const isOpen = openIndex === globalIdx;

          return (
            <div
              key={globalIdx}
              className="sharetopus-card rounded-2xl border-[1.5px] border-[#D6D5CF] dark:border-slate-700 bg-white dark:bg-[#131A29] overflow-hidden transition-all"
            >
              <button
                type="button"
                onClick={() => setOpenIndex(isOpen ? null : globalIdx)}
                className="w-full flex items-center gap-3 px-5 py-4 text-left"
                aria-expanded={isOpen}
              >
                <span className="shrink-0">{item.icon}</span>
                <span className="flex-1 text-sm font-extrabold text-[#1C1B18] dark:text-white">
                  {item.question}
                </span>
                {isOpen ? (
                  <ChevronDown className="w-4 h-4 text-[#736F66] dark:text-[#94A3B8] shrink-0" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-[#736F66] dark:text-[#94A3B8] shrink-0" />
                )}
              </button>
              {isOpen && (
                <div className="px-5 pb-5 pt-0">
                  <div className="pl-7 text-xs font-bold text-[#4A4845] dark:text-[#B8C4D2] leading-relaxed">
                    {item.answer}
                  </div>
                  <div className="pl-7 mt-3">
                    <span className="inline-block px-2 py-0.5 rounded-full bg-[#F3F4EF] dark:bg-[#0F1624] text-[10px] font-extrabold text-[#736F66] dark:text-[#94A3B8] uppercase tracking-wider">
                      {item.category}
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer note */}
      <div className="mt-10 text-center text-xs font-bold text-[#736F66] dark:text-[#94A3B8]">
        <p>
          Can't find your answer? Check the{' '}
          <a
            href="https://github.com/bagusardin25/DevRadar"
            target="_blank"
            rel="noreferrer"
            className="text-[#FF5A36] hover:underline"
          >
            GitHub repository
          </a>{' '}
          or open an issue.
        </p>
      </div>
    </div>
  );
}
