import React from 'react';
import { Globe, LayoutGrid, List, Moon, Sun } from 'lucide-react';

interface HeaderPreferencesProps {
  isOpen: boolean;
  viewLayout: 'grid' | 'compact';
  setViewLayout: (layout: 'grid' | 'compact') => void;
  theme: 'light' | 'dark';
  setTheme: (theme: 'light' | 'dark') => void;
  onOpenExtensionPanel: () => void;
  onClose: () => void;
}

const optionBase =
  'flex items-center justify-center gap-2 rounded-xl border px-3 py-2.5 text-xs font-extrabold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#D23B14]';
const optionIdle =
  'border-[#D6D5CF] text-[#4A4845] hover:border-[#1C1B18] dark:border-slate-700 dark:text-[#B8C4D2] dark:hover:border-[#D6DCE5]';

export const HeaderPreferences: React.FC<HeaderPreferencesProps> = ({
  isOpen,
  viewLayout,
  setViewLayout,
  theme,
  setTheme,
  onOpenExtensionPanel,
  onClose,
}) => {
  if (!isOpen) return null;

  return (
    <div
      id="header-preferences"
      role="dialog"
      aria-labelledby="header-preferences-title"
      aria-describedby="header-preferences-description"
      className="fixed left-3 right-3 top-[6.5rem] z-50 w-auto rounded-2xl border-[1.5px] border-[#1C1B18] bg-white p-4 text-[#1C1B18] shadow-[4px_4px_0_0_#1C1B18] sm:absolute sm:left-auto sm:right-0 sm:top-full sm:mt-3 sm:w-[19rem] dark:border-[#D6DCE5] dark:bg-[#131A29] dark:text-white dark:shadow-[4px_4px_0_0_#D6DCE5]"
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 id="header-preferences-title" className="text-sm font-extrabold">
            Preferences
          </h2>
          <p
            id="header-preferences-description"
            className="mt-0.5 text-[11px] font-semibold text-[#736F66] dark:text-[#94A3B8]"
          >
            Tune the catalogue to your workflow.
          </p>
        </div>
        <span className="rounded-full bg-[#E5E6DF] px-2 py-1 text-[9px] font-extrabold uppercase tracking-wide text-[#4A4845] dark:bg-slate-800 dark:text-[#B8C4D2]">
          Local
        </span>
      </div>

      <div className="space-y-4">
        <fieldset>
          <legend className="mb-2 text-[10px] font-extrabold uppercase tracking-[0.12em] text-[#736F66] dark:text-[#94A3B8]">
            Layout
          </legend>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setViewLayout('grid')}
              aria-pressed={viewLayout === 'grid'}
              className={`${optionBase} ${
                viewLayout === 'grid'
                  ? 'border-[#D23B14] bg-[#FFF1EE] text-[#B83212] dark:bg-[#D23B14]/20 dark:text-[#FF8A6B]'
                  : optionIdle
              }`}
            >
              <LayoutGrid className="h-4 w-4" />
              Grid
            </button>
            <button
              type="button"
              onClick={() => setViewLayout('compact')}
              aria-pressed={viewLayout === 'compact'}
              className={`${optionBase} ${
                viewLayout === 'compact'
                  ? 'border-[#D23B14] bg-[#FFF1EE] text-[#B83212] dark:bg-[#D23B14]/20 dark:text-[#FF8A6B]'
                  : optionIdle
              }`}
            >
              <List className="h-4 w-4" />
              Compact
            </button>
          </div>
        </fieldset>

        <fieldset>
          <legend className="mb-2 text-[10px] font-extrabold uppercase tracking-[0.12em] text-[#736F66] dark:text-[#94A3B8]">
            Theme
          </legend>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setTheme('light')}
              aria-pressed={theme === 'light'}
              className={`${optionBase} ${
                theme === 'light'
                  ? 'border-[#D97706] bg-[#FFFBEB] text-[#92400E] dark:bg-[#D97706]/20 dark:text-[#FBBF24]'
                  : optionIdle
              }`}
            >
              <Sun className="h-4 w-4" />
              Light
            </button>
            <button
              type="button"
              onClick={() => setTheme('dark')}
              aria-pressed={theme === 'dark'}
              className={`${optionBase} ${
                theme === 'dark'
                  ? 'border-[#7C3AED] bg-[#7C3AED]/10 text-[#6D28D9] dark:bg-[#7C3AED]/20 dark:text-[#C4B5FD]'
                  : optionIdle
              }`}
            >
              <Moon className="h-4 w-4" />
              Dark
            </button>
          </div>
        </fieldset>

        <div className="flex items-center justify-between rounded-xl bg-[#F3F4EF] px-3 py-2.5 dark:bg-[#090C15]">
          <span className="text-xs font-extrabold">Language</span>
          <span className="text-[11px] font-bold text-[#736F66] dark:text-[#94A3B8]">
            English only
          </span>
        </div>

        <div className="border-t border-[#D6D5CF] pt-3 dark:border-slate-700">
          <p className="mb-2 text-[10px] font-extrabold uppercase tracking-[0.12em] text-[#736F66] dark:text-[#94A3B8]">
            Project
          </p>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => {
                onClose();
                onOpenExtensionPanel();
              }}
              className={`${optionBase} ${optionIdle}`}
            >
              <Globe className="h-4 w-4" />
              Extension
            </button>
            <a
              href="https://github.com/bagusardin25/DevRadar.git"
              target="_blank"
              rel="noreferrer"
              onClick={onClose}
              aria-label="DevRadar on GitHub (opens in a new tab)"
              className={`${optionBase} ${optionIdle}`}
            >
              <svg className="h-4 w-4 fill-current" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
              </svg>
              GitHub
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};
