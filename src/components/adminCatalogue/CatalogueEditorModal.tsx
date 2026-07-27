import React, { useEffect, useState } from 'react';
import { AlertCircle, Loader2, X } from 'lucide-react';
import type {
  AdminAIOfferRecord,
  AdminHackathonRecord,
} from '../../api/adminCatalogue';
import { useModalA11y } from '../../hooks/useModalA11y';
import {
  EFFORT_OPTIONS,
  MODE_OPTIONS,
  OFFER_TYPE_OPTIONS,
  VERIFICATION_OPTIONS,
  makeAIOfferForm,
  makeHackathonForm,
  slugify,
  type AIOfferFormState,
  type HackathonFormState,
} from './formState';

type EditorKind = 'hackathon' | 'ai_offer';

type CatalogueEditorProps = {
  kind: EditorKind;
  hackathon?: AdminHackathonRecord;
  aiOffer?: AdminAIOfferRecord;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onSaveHackathon: (form: HackathonFormState) => Promise<void>;
  onSaveAIOffer: (form: AIOfferFormState) => Promise<void>;
};

const inputClass =
  'w-full rounded-xl border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#131A29] px-3 py-2.5 text-sm font-semibold text-[#1C1B18] dark:text-white outline-none transition-shadow focus:shadow-[3px_3px_0_0_#1C1B18] dark:focus:shadow-[3px_3px_0_0_#D6DCE5] disabled:opacity-60';

function Field({
  label,
  hint,
  children,
  full = false,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
  full?: boolean;
}) {
  return (
    <label className={`block space-y-1.5 ${full ? 'md:col-span-2' : ''}`}>
      <span className="text-xs font-extrabold text-[#1C1B18] dark:text-white">{label}</span>
      {children}
      {hint && (
        <span className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400">
          {hint}
        </span>
      )}
    </label>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <fieldset className="space-y-3">
      <legend className="w-full border-b border-[#D6D5CF] dark:border-slate-700 pb-2 text-base font-extrabold text-[#1C1B18] dark:text-white">
        {title}
      </legend>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{children}</div>
    </fieldset>
  );
}

export const CatalogueEditorModal: React.FC<CatalogueEditorProps> = ({
  kind,
  hackathon,
  aiOffer,
  busy,
  error,
  onClose,
  onSaveHackathon,
  onSaveAIOffer,
}) => {
  const [hackathonForm, setHackathonForm] = useState(() => makeHackathonForm(hackathon));
  const [aiForm, setAIForm] = useState(() => makeAIOfferForm(aiOffer));
  const [validationError, setValidationError] = useState<string | null>(null);
  const dialogRef = useModalA11y(true, onClose);

  useEffect(() => {
    setHackathonForm(makeHackathonForm(hackathon));
    setAIForm(makeAIOfferForm(aiOffer));
    setValidationError(null);
  }, [kind, hackathon, aiOffer]);

  const editing = kind === 'hackathon' ? Boolean(hackathon) : Boolean(aiOffer);
  const title = `${editing ? 'Edit' : 'Add'} ${kind === 'hackathon' ? 'Hackathon' : 'AI Promo'}`;
  const helper =
    kind === 'hackathon'
      ? 'Update the public listing and publishing status.'
      : 'Publish a verified AI offer for developers.';
  const accent = kind === 'hackathon' ? '#D23B14' : '#7C3AED';

  const handleHackathonTitle = (value: string) => {
    setHackathonForm((current) => ({
      ...current,
      title: value,
      slug:
        !hackathon && (!current.slug || current.slug === slugify(current.title))
          ? slugify(value)
          : current.slug,
    }));
  };

  const handleAITitle = (value: string) => {
    setAIForm((current) => ({
      ...current,
      title: value,
      slug:
        !aiOffer && (!current.slug || current.slug === slugify(current.title))
          ? slugify(value)
          : current.slug,
    }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setValidationError(null);
    if (kind === 'hackathon') {
      if (Number(hackathonForm.teamMax) < Number(hackathonForm.teamMin)) {
        setValidationError('Team max must be greater than or equal to team min.');
        return;
      }
      await onSaveHackathon(hackathonForm);
      return;
    }
    await onSaveAIOffer(aiForm);
  };

  const visibleError = validationError || error;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-[#1C1B18]/55 p-3 sm:p-6 backdrop-blur-[2px]">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="catalogue-editor-title"
        className="flex max-h-[94vh] w-full max-w-5xl flex-col overflow-hidden rounded-[24px] border-[1.5px] border-[#1C1B18] dark:border-[#D6DCE5] bg-white dark:bg-[#0F1624] shadow-[5px_5px_0_0_#1C1B18] dark:shadow-[5px_5px_0_0_#D6DCE5]"
      >
        <div className="flex items-start justify-between gap-4 border-b border-[#D6D5CF] dark:border-slate-700 px-5 py-4 sm:px-7">
          <div>
            <h2
              id="catalogue-editor-title"
              className="text-2xl font-extrabold tracking-[-0.03em] text-[#1C1B18] dark:text-white"
            >
              {title}
            </h2>
            <p className="mt-1 text-xs font-semibold text-slate-600 dark:text-slate-300">
              {helper}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            aria-label="Close editor"
            className="rounded-full p-2 text-[#1C1B18] hover:bg-[#F3F4EF] dark:text-white dark:hover:bg-[#1A2336]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 py-5 sm:px-7">
            {visibleError && (
              <div className="flex items-start gap-2 rounded-xl border-[1.5px] border-[#FF5A36] bg-[#FF5A36]/10 p-3 text-xs font-bold text-[#1C1B18] dark:text-white">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-[#FF5A36]" />
                <span>{visibleError}</span>
              </div>
            )}

            {kind === 'hackathon' ? (
              <>
                <Section title="Basics">
                  <Field label="Title">
                    <input
                      className={inputClass}
                      value={hackathonForm.title}
                      onChange={(event) => handleHackathonTitle(event.target.value)}
                      required
                      autoFocus
                    />
                  </Field>
                  <Field label="Slug" hint="Lowercase letters, numbers, and hyphens only.">
                    <input
                      className={inputClass}
                      value={hackathonForm.slug}
                      onChange={(event) =>
                        setHackathonForm((form) => ({ ...form, slug: event.target.value }))
                      }
                      pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
                      required
                    />
                  </Field>
                  <Field label="Organizer">
                    <input
                      className={inputClass}
                      value={hackathonForm.organizer}
                      onChange={(event) =>
                        setHackathonForm((form) => ({ ...form, organizer: event.target.value }))
                      }
                      required
                    />
                  </Field>
                  <Field label="Organizer logo URL">
                    <input
                      type="url"
                      className={inputClass}
                      value={hackathonForm.organizerLogo}
                      onChange={(event) =>
                        setHackathonForm((form) => ({ ...form, organizerLogo: event.target.value }))
                      }
                    />
                  </Field>
                  <Field label="Description" full>
                    <textarea
                      className={`${inputClass} min-h-24 resize-y`}
                      value={hackathonForm.description}
                      onChange={(event) =>
                        setHackathonForm((form) => ({ ...form, description: event.target.value }))
                      }
                    />
                  </Field>
                </Section>

                <Section title="Schedule & participation">
                  <Field label="Registration opens">
                    <input
                      type="datetime-local"
                      className={inputClass}
                      value={hackathonForm.registrationOpenAt}
                      onChange={(event) =>
                        setHackathonForm((form) => ({
                          ...form,
                          registrationOpenAt: event.target.value,
                        }))
                      }
                    />
                  </Field>
                  <Field label="Registration deadline">
                    <input
                      type="datetime-local"
                      className={inputClass}
                      value={hackathonForm.registrationDeadline}
                      onChange={(event) =>
                        setHackathonForm((form) => ({
                          ...form,
                          registrationDeadline: event.target.value,
                        }))
                      }
                    />
                  </Field>
                  <Field label="Submission deadline">
                    <input
                      type="datetime-local"
                      className={inputClass}
                      value={hackathonForm.submissionDeadline}
                      onChange={(event) =>
                        setHackathonForm((form) => ({
                          ...form,
                          submissionDeadline: event.target.value,
                        }))
                      }
                    />
                  </Field>
                  <Field label="Mode">
                    <select
                      className={inputClass}
                      value={hackathonForm.mode}
                      onChange={(event) =>
                        setHackathonForm((form) => ({
                          ...form,
                          mode: event.target.value as HackathonFormState['mode'],
                        }))
                      }
                    >
                      {MODE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Location">
                    <input
                      className={inputClass}
                      value={hackathonForm.location}
                      onChange={(event) =>
                        setHackathonForm((form) => ({ ...form, location: event.target.value }))
                      }
                    />
                  </Field>
                  <Field label="Eligible countries" hint="Comma-separated values.">
                    <input
                      className={inputClass}
                      value={hackathonForm.eligibleCountries}
                      onChange={(event) =>
                        setHackathonForm((form) => ({
                          ...form,
                          eligibleCountries: event.target.value,
                        }))
                      }
                    />
                  </Field>
                  <Field label="Eligibility" hint="Comma-separated values." full>
                    <input
                      className={inputClass}
                      value={hackathonForm.eligibility}
                      onChange={(event) =>
                        setHackathonForm((form) => ({ ...form, eligibility: event.target.value }))
                      }
                    />
                  </Field>
                  <Field label="Team min">
                    <input
                      type="number"
                      min="1"
                      className={inputClass}
                      value={hackathonForm.teamMin}
                      onChange={(event) =>
                        setHackathonForm((form) => ({ ...form, teamMin: event.target.value }))
                      }
                      required
                    />
                  </Field>
                  <Field label="Team max">
                    <input
                      type="number"
                      min="1"
                      className={inputClass}
                      value={hackathonForm.teamMax}
                      onChange={(event) =>
                        setHackathonForm((form) => ({ ...form, teamMax: event.target.value }))
                      }
                      required
                    />
                  </Field>
                </Section>

                <Section title="Prize & fit">
                  <Field label="Prize value">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      className={inputClass}
                      value={hackathonForm.prizeValue}
                      onChange={(event) =>
                        setHackathonForm((form) => ({ ...form, prizeValue: event.target.value }))
                      }
                      required
                    />
                  </Field>
                  <Field label="Currency">
                    <input
                      className={inputClass}
                      value={hackathonForm.prizeCurrency}
                      onChange={(event) =>
                        setHackathonForm((form) => ({
                          ...form,
                          prizeCurrency: event.target.value.toUpperCase(),
                        }))
                      }
                      maxLength={8}
                    />
                  </Field>
                  <Field label="Prize label" full>
                    <input
                      className={inputClass}
                      value={hackathonForm.prizeLabel}
                      onChange={(event) =>
                        setHackathonForm((form) => ({ ...form, prizeLabel: event.target.value }))
                      }
                      placeholder="TBA, Free entry, or $30K + credits"
                    />
                  </Field>
                  <Field label="Technologies" hint="Comma-separated values." full>
                    <input
                      className={inputClass}
                      value={hackathonForm.technologies}
                      onChange={(event) =>
                        setHackathonForm((form) => ({ ...form, technologies: event.target.value }))
                      }
                    />
                  </Field>
                  <Field label="Official URL">
                    <input
                      type="url"
                      className={inputClass}
                      value={hackathonForm.officialUrl}
                      onChange={(event) =>
                        setHackathonForm((form) => ({ ...form, officialUrl: event.target.value }))
                      }
                      required
                    />
                  </Field>
                  <Field label="Suitable reasons" hint="Comma-separated values.">
                    <input
                      className={inputClass}
                      value={hackathonForm.suitableReasons}
                      onChange={(event) =>
                        setHackathonForm((form) => ({
                          ...form,
                          suitableReasons: event.target.value,
                        }))
                      }
                    />
                  </Field>
                  <Field label="Effort estimate">
                    <select
                      className={inputClass}
                      value={hackathonForm.effortEstimate}
                      onChange={(event) =>
                        setHackathonForm((form) => ({
                          ...form,
                          effortEstimate: event.target.value as HackathonFormState['effortEstimate'],
                        }))
                      }
                    >
                      <option value="">Not specified</option>
                      {EFFORT_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                </Section>
              </>
            ) : (
              <>
                <Section title="Basics">
                  <Field label="Listing title">
                    <input
                      className={inputClass}
                      value={aiForm.title}
                      onChange={(event) => handleAITitle(event.target.value)}
                      required
                      autoFocus
                    />
                  </Field>
                  <Field label="Slug" hint="Lowercase letters, numbers, and hyphens only.">
                    <input
                      className={inputClass}
                      value={aiForm.slug}
                      onChange={(event) =>
                        setAIForm((form) => ({ ...form, slug: event.target.value }))
                      }
                      pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
                      required
                    />
                  </Field>
                  <Field label="Product name">
                    <input
                      className={inputClass}
                      value={aiForm.productName}
                      onChange={(event) =>
                        setAIForm((form) => ({ ...form, productName: event.target.value }))
                      }
                      required
                    />
                  </Field>
                  <Field label="Provider">
                    <input
                      className={inputClass}
                      value={aiForm.provider}
                      onChange={(event) =>
                        setAIForm((form) => ({ ...form, provider: event.target.value }))
                      }
                      required
                    />
                  </Field>
                  <Field label="Provider logo URL" full>
                    <input
                      type="url"
                      className={inputClass}
                      value={aiForm.providerLogo}
                      onChange={(event) =>
                        setAIForm((form) => ({ ...form, providerLogo: event.target.value }))
                      }
                    />
                  </Field>
                  <Field label="Description" full>
                    <textarea
                      className={`${inputClass} min-h-24 resize-y`}
                      value={aiForm.description}
                      onChange={(event) =>
                        setAIForm((form) => ({ ...form, description: event.target.value }))
                      }
                    />
                  </Field>
                </Section>

                <Section title="Offer details">
                  <Field label="Offer type">
                    <select
                      className={inputClass}
                      value={aiForm.offerType}
                      onChange={(event) =>
                        setAIForm((form) => ({
                          ...form,
                          offerType: event.target.value as AIOfferFormState['offerType'],
                        }))
                      }
                    >
                      {OFFER_TYPE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Offer value">
                    <input
                      className={inputClass}
                      value={aiForm.offerValue}
                      onChange={(event) =>
                        setAIForm((form) => ({ ...form, offerValue: event.target.value }))
                      }
                    />
                  </Field>
                  <Field label="Target users" hint="Comma-separated values.">
                    <input
                      className={inputClass}
                      value={aiForm.targetUsers}
                      onChange={(event) =>
                        setAIForm((form) => ({ ...form, targetUsers: event.target.value }))
                      }
                    />
                  </Field>
                  <Field label="Requirements" hint="Comma-separated values.">
                    <input
                      className={inputClass}
                      value={aiForm.requirements}
                      onChange={(event) =>
                        setAIForm((form) => ({ ...form, requirements: event.target.value }))
                      }
                    />
                  </Field>
                  <Field label="Tags" hint="Comma-separated values.">
                    <input
                      className={inputClass}
                      value={aiForm.tags}
                      onChange={(event) =>
                        setAIForm((form) => ({ ...form, tags: event.target.value }))
                      }
                    />
                  </Field>
                  <Field label="Suitable reasons" hint="Comma-separated values.">
                    <input
                      className={inputClass}
                      value={aiForm.suitableReasons}
                      onChange={(event) =>
                        setAIForm((form) => ({ ...form, suitableReasons: event.target.value }))
                      }
                    />
                  </Field>
                </Section>

                <Section title="Availability">
                  <Field label="Starts at">
                    <input
                      type="datetime-local"
                      className={inputClass}
                      value={aiForm.startsAt}
                      onChange={(event) =>
                        setAIForm((form) => ({ ...form, startsAt: event.target.value }))
                      }
                    />
                  </Field>
                  <Field label="Expires at">
                    <input
                      type="datetime-local"
                      className={inputClass}
                      value={aiForm.expiresAt}
                      onChange={(event) =>
                        setAIForm((form) => ({ ...form, expiresAt: event.target.value }))
                      }
                    />
                  </Field>
                  <Field label="Supported regions" hint="Comma-separated values." full>
                    <input
                      className={inputClass}
                      value={aiForm.supportedRegions}
                      onChange={(event) =>
                        setAIForm((form) => ({ ...form, supportedRegions: event.target.value }))
                      }
                    />
                  </Field>
                  <Field label="Official terms URL">
                    <input
                      type="url"
                      className={inputClass}
                      value={aiForm.officialTermsUrl}
                      onChange={(event) =>
                        setAIForm((form) => ({ ...form, officialTermsUrl: event.target.value }))
                      }
                      required
                    />
                  </Field>
                  <Field label="Claim URL">
                    <input
                      type="url"
                      className={inputClass}
                      value={aiForm.claimUrl}
                      onChange={(event) =>
                        setAIForm((form) => ({ ...form, claimUrl: event.target.value }))
                      }
                      required
                    />
                  </Field>
                </Section>
              </>
            )}

            <Section title="Publishing">
              <Field label="Verification status">
                <select
                  className={inputClass}
                  value={kind === 'hackathon' ? hackathonForm.verificationStatus : aiForm.verificationStatus}
                  onChange={(event) => {
                    const value = event.target.value as HackathonFormState['verificationStatus'];
                    if (kind === 'hackathon') {
                      setHackathonForm((form) => ({ ...form, verificationStatus: value }));
                    } else {
                      setAIForm((form) => ({ ...form, verificationStatus: value }));
                    }
                  }}
                >
                  {VERIFICATION_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Confidence score" hint="Enter a value from 0.00 to 1.00.">
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  className={inputClass}
                  value={kind === 'hackathon' ? hackathonForm.confidenceScore : aiForm.confidenceScore}
                  onChange={(event) => {
                    if (kind === 'hackathon') {
                      setHackathonForm((form) => ({ ...form, confidenceScore: event.target.value }));
                    } else {
                      setAIForm((form) => ({ ...form, confidenceScore: event.target.value }));
                    }
                  }}
                  required
                />
              </Field>
            </Section>
          </div>

          <div className="flex items-center justify-end gap-3 border-t border-[#D6D5CF] dark:border-slate-700 bg-white dark:bg-[#0F1624] px-5 py-4 sm:px-7">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="btn-sharetopus-secondary px-5 py-2.5 text-sm font-extrabold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy}
              className="inline-flex items-center justify-center gap-2 rounded-xl border-[1.5px] border-[#1C1B18] px-5 py-2.5 text-sm font-extrabold text-white shadow-[3px_3px_0_0_#1C1B18] transition-transform hover:-translate-y-0.5 disabled:cursor-wait disabled:opacity-60"
              style={{ backgroundColor: accent }}
            >
              {busy && <Loader2 className="h-4 w-4 animate-spin" />}
              {editing
                ? 'Save changes'
                : kind === 'hackathon'
                  ? 'Create Hackathon'
                  : 'Create AI Promo'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
