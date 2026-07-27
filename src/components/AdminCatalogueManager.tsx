import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Code2,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react';
import type { AdminMe } from '../api';
import {
  createAdminAIOffer,
  createAdminHackathon,
  deleteAdminAIOffer,
  deleteAdminHackathon,
  fetchAdminAIOffers,
  fetchAdminHackathons,
  updateAdminAIOffer,
  updateAdminHackathon,
  type AdminAIOfferRecord,
  type AdminHackathonRecord,
} from '../api/adminCatalogue';
import type { VerificationStatus } from '../types';
import { useModalA11y } from '../hooks/useModalA11y';
import { CatalogueEditorModal } from './adminCatalogue/CatalogueEditorModal';
import {
  aiOfferFormToInput,
  hackathonFormToInput,
  VERIFICATION_OPTIONS,
  type AIOfferFormState,
  type HackathonFormState,
} from './adminCatalogue/formState';

type Tab = 'hackathon' | 'ai_offer';
type EditorState =
  | { kind: 'hackathon'; record?: AdminHackathonRecord }
  | { kind: 'ai_offer'; record?: AdminAIOfferRecord };
type DeleteTarget =
  | { kind: 'hackathon'; id: string; title: string }
  | { kind: 'ai_offer'; id: string; title: string };

interface AdminCatalogueManagerProps {
  admin: AdminMe;
  onCatalogueChanged: () => void;
}

const STATUS_STYLE: Record<VerificationStatus, string> = {
  verified_active: 'border-[#059669] bg-[#059669]/10 text-[#047857] dark:text-[#34D399]',
  likely_active: 'border-[#0284C7] bg-[#0284C7]/10 text-[#0369A1] dark:text-[#7DD3FC]',
  needs_review: 'border-[#D97706] bg-[#D97706]/10 text-[#B45309] dark:text-[#FBBF24]',
  registration_closed: 'border-slate-500 bg-slate-500/10 text-slate-700 dark:text-slate-300',
  expired: 'border-slate-500 bg-slate-500/10 text-slate-700 dark:text-slate-300',
  cancelled: 'border-[#FF5A36] bg-[#FF5A36]/10 text-[#C2410C] dark:text-[#FF8A6B]',
};

function statusLabel(status: VerificationStatus): string {
  return VERIFICATION_OPTIONS.find((option) => option.value === status)?.label ?? status;
}

function StatusBadge({ status }: { status: VerificationStatus }) {
  return (
    <span
      className={`inline-flex whitespace-nowrap rounded-full border px-2.5 py-1 text-[11px] font-extrabold ${STATUS_STYLE[status]}`}
    >
      {statusLabel(status)}
    </span>
  );
}

function formatDate(value: string | null): string {
  if (!value) return 'Not set';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Not set';
  return new Intl.DateTimeFormat('en', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(date);
}

function DeleteConfirmModal({
  target,
  busy,
  error,
  onCancel,
  onConfirm,
}: {
  target: DeleteTarget;
  busy: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const dialogRef = useModalA11y(true, onCancel);
  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-[#1C1B18]/60 p-4 backdrop-blur-[2px]">
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="delete-catalogue-title"
        className="w-full max-w-md rounded-[24px] border-[1.5px] border-[#1C1B18] bg-white p-6 shadow-[5px_5px_0_0_#1C1B18] dark:border-[#D6DCE5] dark:bg-[#131A29] dark:shadow-[5px_5px_0_0_#D6DCE5]"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="delete-catalogue-title" className="text-xl font-extrabold text-[#1C1B18] dark:text-white">
              Delete {target.kind === 'hackathon' ? 'Hackathon' : 'AI Promo'}?
            </h2>
            <p className="mt-2 text-sm font-semibold text-slate-700 dark:text-slate-300">
              <strong>{target.title}</strong> will be removed from the catalogue permanently.
            </p>
          </div>
          <button type="button" onClick={onCancel} disabled={busy} aria-label="Close confirmation">
            <X className="h-5 w-5" />
          </button>
        </div>
        {error && (
          <p className="mt-4 rounded-xl border border-[#FF5A36] bg-[#FF5A36]/10 p-3 text-xs font-bold text-[#C2410C] dark:text-[#FF8A6B]">
            {error}
          </p>
        )}
        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="btn-sharetopus-secondary px-4 py-2 text-xs font-extrabold"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="inline-flex items-center gap-2 rounded-xl border-[1.5px] border-[#1C1B18] bg-[#D23B14] px-4 py-2 text-xs font-extrabold text-white shadow-[3px_3px_0_0_#1C1B18] disabled:opacity-60"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
            Delete permanently
          </button>
        </div>
      </div>
    </div>
  );
}

export const AdminCatalogueManager: React.FC<AdminCatalogueManagerProps> = ({
  admin,
  onCatalogueChanged,
}) => {
  const [tab, setTab] = useState<Tab>('hackathon');
  const [hackathons, setHackathons] = useState<AdminHackathonRecord[]>([]);
  const [aiOffers, setAIOffers] = useState<AdminAIOfferRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<VerificationStatus | 'all'>('all');
  const [editor, setEditor] = useState<EditorState | null>(null);
  const [editorBusy, setEditorBusy] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [hackathonResult, offerResult] = await Promise.all([
        fetchAdminHackathons(),
        fetchAdminAIOffers(),
      ]);
      setHackathons(hackathonResult.items);
      setAIOffers(offerResult.items);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Failed to load admin catalogue.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const filteredHackathons = useMemo(() => {
    const term = search.trim().toLowerCase();
    return hackathons.filter((item) => {
      const matchesTerm =
        !term ||
        item.listing.title.toLowerCase().includes(term) ||
        item.listing.slug.toLowerCase().includes(term) ||
        item.hackathon.organizer.toLowerCase().includes(term);
      const matchesStatus = status === 'all' || item.listing.verificationStatus === status;
      return matchesTerm && matchesStatus;
    });
  }, [hackathons, search, status]);

  const filteredOffers = useMemo(() => {
    const term = search.trim().toLowerCase();
    return aiOffers.filter((item) => {
      const matchesTerm =
        !term ||
        item.listing.title.toLowerCase().includes(term) ||
        item.listing.slug.toLowerCase().includes(term) ||
        item.aiOffer.productName.toLowerCase().includes(term) ||
        item.aiOffer.provider.toLowerCase().includes(term);
      const matchesStatus = status === 'all' || item.listing.verificationStatus === status;
      return matchesTerm && matchesStatus;
    });
  }, [aiOffers, search, status]);

  const closeEditor = () => {
    if (editorBusy) return;
    setEditor(null);
    setEditorError(null);
  };

  const afterMutation = async () => {
    await loadData();
    onCatalogueChanged();
  };

  const saveHackathon = async (form: HackathonFormState) => {
    setEditorBusy(true);
    setEditorError(null);
    try {
      const input = hackathonFormToInput(form);
      if (editor?.kind === 'hackathon' && editor.record) {
        await updateAdminHackathon(editor.record.listing.id, input, admin.csrfToken);
      } else {
        await createAdminHackathon(input, admin.csrfToken);
      }
      setEditor(null);
      await afterMutation();
    } catch (caught) {
      setEditorError(caught instanceof Error ? caught.message : 'Failed to save hackathon.');
    } finally {
      setEditorBusy(false);
    }
  };

  const saveAIOffer = async (form: AIOfferFormState) => {
    setEditorBusy(true);
    setEditorError(null);
    try {
      const input = aiOfferFormToInput(form);
      if (editor?.kind === 'ai_offer' && editor.record) {
        await updateAdminAIOffer(editor.record.listing.id, input, admin.csrfToken);
      } else {
        await createAdminAIOffer(input, admin.csrfToken);
      }
      setEditor(null);
      await afterMutation();
    } catch (caught) {
      setEditorError(caught instanceof Error ? caught.message : 'Failed to save AI promo.');
    } finally {
      setEditorBusy(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      if (deleteTarget.kind === 'hackathon') {
        await deleteAdminHackathon(deleteTarget.id, admin.csrfToken);
      } else {
        await deleteAdminAIOffer(deleteTarget.id, admin.csrfToken);
      }
      setDeleteTarget(null);
      await afterMutation();
    } catch (caught) {
      setDeleteError(caught instanceof Error ? caught.message : 'Failed to delete catalogue item.');
    } finally {
      setDeleteBusy(false);
    }
  };

  const rows = tab === 'hackathon' ? filteredHackathons : filteredOffers;

  return (
    <div className="mx-auto max-w-6xl space-y-5 px-4 py-6 font-sans lg:px-8">
      <section className="rounded-[28px] border-[1.5px] border-[#1C1B18] bg-white p-5 shadow-[4px_4px_0_0_#1C1B18] dark:border-[#D6DCE5] dark:bg-[#131A29] dark:shadow-[4px_4px_0_0_#D6DCE5] sm:p-7">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-2xl font-extrabold tracking-[-0.03em] text-[#1C1B18] dark:text-white sm:text-3xl">
              Catalogue Manager
            </h2>
            <p className="mt-1 text-sm font-semibold text-slate-700 dark:text-slate-300">
              Create, review, update, and remove public opportunities.
            </p>
            <p className="mt-2 font-mono text-[11px] font-bold text-slate-500 dark:text-slate-400">
              Signed in as {admin.email}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => {
                setEditorError(null);
                setEditor({ kind: 'hackathon' });
              }}
              className="inline-flex items-center gap-2 rounded-xl border-[1.5px] border-[#1C1B18] bg-white px-4 py-2.5 text-xs font-extrabold text-[#D23B14] shadow-[3px_3px_0_0_#1C1B18] transition-transform hover:-translate-y-0.5 dark:bg-[#131A29]"
            >
              <Plus className="h-4 w-4" />
              Add Hackathon
            </button>
            <button
              type="button"
              onClick={() => {
                setEditorError(null);
                setEditor({ kind: 'ai_offer' });
              }}
              className="inline-flex items-center gap-2 rounded-xl border-[1.5px] border-[#1C1B18] bg-white px-4 py-2.5 text-xs font-extrabold text-[#7C3AED] shadow-[3px_3px_0_0_#1C1B18] transition-transform hover:-translate-y-0.5 dark:bg-[#131A29]"
            >
              <Plus className="h-4 w-4" />
              Add AI Promo
            </button>
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-4">
          <div className="inline-flex w-fit rounded-xl border-[1.5px] border-[#1C1B18] bg-[#F3F4EF] p-1 dark:border-[#D6DCE5] dark:bg-[#0F1624]">
            <button
              type="button"
              onClick={() => setTab('hackathon')}
              aria-pressed={tab === 'hackathon'}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-extrabold transition-colors ${
                tab === 'hackathon'
                  ? 'bg-white text-[#D23B14] shadow-sm dark:bg-[#1A2336]'
                  : 'text-slate-600 dark:text-slate-300'
              }`}
            >
              <Code2 className="h-4 w-4" />
              Hackathons
              <span className="font-mono text-[10px]">{hackathons.length}</span>
            </button>
            <button
              type="button"
              onClick={() => setTab('ai_offer')}
              aria-pressed={tab === 'ai_offer'}
              className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-extrabold transition-colors ${
                tab === 'ai_offer'
                  ? 'bg-white text-[#7C3AED] shadow-sm dark:bg-[#1A2336]'
                  : 'text-slate-600 dark:text-slate-300'
              }`}
            >
              <Sparkles className="h-4 w-4" />
              AI Promos
              <span className="font-mono text-[10px]">{aiOffers.length}</span>
            </button>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <label className="relative min-w-0 flex-1">
              <span className="sr-only">Search catalogue</span>
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search catalogue..."
                className="w-full rounded-xl border-[1.5px] border-[#1C1B18] bg-white py-2.5 pl-10 pr-3 text-sm font-semibold outline-none focus:shadow-[3px_3px_0_0_#1C1B18] dark:border-[#D6DCE5] dark:bg-[#0F1624] dark:text-white"
              />
            </label>
            <label>
              <span className="sr-only">Filter by status</span>
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value as VerificationStatus | 'all')}
                className="w-full rounded-xl border-[1.5px] border-[#1C1B18] bg-white px-3 py-2.5 text-sm font-bold outline-none dark:border-[#D6DCE5] dark:bg-[#0F1624] dark:text-white sm:w-52"
              >
                <option value="all">All statuses</option>
                {VERIFICATION_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => void loadData()}
              disabled={loading}
              className="btn-sharetopus-secondary px-4 py-2.5 text-xs font-extrabold"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>
      </section>

      {error && (
        <div className="flex items-start gap-2 rounded-2xl border-[1.5px] border-[#FF5A36] bg-[#FF5A36]/10 p-4 text-xs font-bold text-[#1C1B18] dark:text-white">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-[#FF5A36]" />
          <span>{error}</span>
        </div>
      )}

      <section className="overflow-hidden rounded-[24px] border-[1.5px] border-[#1C1B18] bg-white shadow-[4px_4px_0_0_#1C1B18] dark:border-[#D6DCE5] dark:bg-[#131A29] dark:shadow-[4px_4px_0_0_#D6DCE5]">
        {loading ? (
          <div className="flex min-h-64 items-center justify-center gap-2 text-sm font-bold text-slate-600 dark:text-slate-300">
            <Loader2 className="h-5 w-5 animate-spin text-[#D23B14]" />
            Loading catalogue...
          </div>
        ) : rows.length === 0 ? (
          <div className="flex min-h-64 flex-col items-center justify-center gap-2 px-6 text-center">
            {tab === 'hackathon' ? (
              <Code2 className="h-9 w-9 text-[#D23B14]" />
            ) : (
              <Sparkles className="h-9 w-9 text-[#7C3AED]" />
            )}
            <h3 className="text-lg font-extrabold text-[#1C1B18] dark:text-white">
              No catalogue entries found
            </h3>
            <p className="text-xs font-semibold text-slate-600 dark:text-slate-300">
              Adjust the search or add a new {tab === 'hackathon' ? 'hackathon' : 'AI promo'}.
            </p>
          </div>
        ) : (
          <>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[820px] border-collapse text-left">
                <thead className="bg-[#F3F4EF] text-xs font-extrabold text-[#1C1B18] dark:bg-[#0F1624] dark:text-white">
                  <tr>
                    <th className="px-5 py-4">Opportunity</th>
                    <th className="px-4 py-4">Status</th>
                    <th className="px-4 py-4">{tab === 'hackathon' ? 'Deadline' : 'Expires'}</th>
                    <th className="px-4 py-4">Updated</th>
                    <th className="px-5 py-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {tab === 'hackathon'
                    ? filteredHackathons.map((item) => (
                        <tr key={item.listing.id} className="border-t border-[#D6D5CF] dark:border-slate-700">
                          <td className="px-5 py-4">
                            <div className="font-extrabold text-[#1C1B18] dark:text-white">{item.listing.title}</div>
                            <div className="mt-1 text-xs font-semibold text-slate-600 dark:text-slate-400">
                              by {item.hackathon.organizer}
                            </div>
                          </td>
                          <td className="px-4 py-4"><StatusBadge status={item.listing.verificationStatus} /></td>
                          <td className="px-4 py-4 text-xs font-bold text-slate-700 dark:text-slate-300">
                            {formatDate(item.hackathon.submissionDeadline)}
                          </td>
                          <td className="px-4 py-4 text-xs font-bold text-slate-700 dark:text-slate-300">
                            {formatDate(item.listing.updatedAt)}
                          </td>
                          <td className="px-5 py-4">
                            <div className="flex justify-end gap-2">
                              <button
                                type="button"
                                title="Edit hackathon"
                                aria-label={`Edit ${item.listing.title}`}
                                onClick={() => setEditor({ kind: 'hackathon', record: item })}
                                className="rounded-xl border-[1.5px] border-[#1C1B18] p-2 text-[#1C1B18] shadow-[2px_2px_0_0_#1C1B18] hover:text-[#D23B14] dark:border-[#D6DCE5] dark:text-white"
                              ><Pencil className="h-4 w-4" /></button>
                              <button
                                type="button"
                                title="Delete hackathon"
                                aria-label={`Delete ${item.listing.title}`}
                                onClick={() => setDeleteTarget({ kind: 'hackathon', id: item.listing.id, title: item.listing.title })}
                                className="rounded-xl border-[1.5px] border-[#1C1B18] p-2 text-[#D23B14] shadow-[2px_2px_0_0_#1C1B18] dark:border-[#D6DCE5]"
                              ><Trash2 className="h-4 w-4" /></button>
                            </div>
                          </td>
                        </tr>
                      ))
                    : filteredOffers.map((item) => (
                        <tr key={item.listing.id} className="border-t border-[#D6D5CF] dark:border-slate-700">
                          <td className="px-5 py-4">
                            <div className="font-extrabold text-[#1C1B18] dark:text-white">{item.listing.title}</div>
                            <div className="mt-1 text-xs font-semibold text-slate-600 dark:text-slate-400">
                              {item.aiOffer.productName} by {item.aiOffer.provider}
                            </div>
                          </td>
                          <td className="px-4 py-4"><StatusBadge status={item.listing.verificationStatus} /></td>
                          <td className="px-4 py-4 text-xs font-bold text-slate-700 dark:text-slate-300">
                            {formatDate(item.aiOffer.expiresAt)}
                          </td>
                          <td className="px-4 py-4 text-xs font-bold text-slate-700 dark:text-slate-300">
                            {formatDate(item.listing.updatedAt)}
                          </td>
                          <td className="px-5 py-4">
                            <div className="flex justify-end gap-2">
                              <button
                                type="button"
                                title="Edit AI promo"
                                aria-label={`Edit ${item.listing.title}`}
                                onClick={() => setEditor({ kind: 'ai_offer', record: item })}
                                className="rounded-xl border-[1.5px] border-[#1C1B18] p-2 text-[#1C1B18] shadow-[2px_2px_0_0_#1C1B18] hover:text-[#7C3AED] dark:border-[#D6DCE5] dark:text-white"
                              ><Pencil className="h-4 w-4" /></button>
                              <button
                                type="button"
                                title="Delete AI promo"
                                aria-label={`Delete ${item.listing.title}`}
                                onClick={() => setDeleteTarget({ kind: 'ai_offer', id: item.listing.id, title: item.listing.title })}
                                className="rounded-xl border-[1.5px] border-[#1C1B18] p-2 text-[#D23B14] shadow-[2px_2px_0_0_#1C1B18] dark:border-[#D6DCE5]"
                              ><Trash2 className="h-4 w-4" /></button>
                            </div>
                          </td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>

            <div className="divide-y divide-[#D6D5CF] dark:divide-slate-700 md:hidden">
              {tab === 'hackathon'
                ? filteredHackathons.map((item) => (
                    <article key={item.listing.id} className="space-y-3 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="font-extrabold text-[#1C1B18] dark:text-white">{item.listing.title}</h3>
                          <p className="mt-1 text-xs font-semibold text-slate-600 dark:text-slate-400">by {item.hackathon.organizer}</p>
                        </div>
                        <StatusBadge status={item.listing.verificationStatus} />
                      </div>
                      <p className="text-xs font-bold text-slate-600 dark:text-slate-300">Deadline: {formatDate(item.hackathon.submissionDeadline)}</p>
                      <div className="flex justify-end gap-2">
                        <button type="button" onClick={() => setEditor({ kind: 'hackathon', record: item })} className="btn-sharetopus-secondary px-3 py-2 text-xs font-extrabold"><Pencil className="h-4 w-4" /> Edit</button>
                        <button type="button" onClick={() => setDeleteTarget({ kind: 'hackathon', id: item.listing.id, title: item.listing.title })} className="rounded-xl border-[1.5px] border-[#1C1B18] px-3 py-2 text-xs font-extrabold text-[#D23B14]"><Trash2 className="inline h-4 w-4" /> Delete</button>
                      </div>
                    </article>
                  ))
                : filteredOffers.map((item) => (
                    <article key={item.listing.id} className="space-y-3 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="font-extrabold text-[#1C1B18] dark:text-white">{item.listing.title}</h3>
                          <p className="mt-1 text-xs font-semibold text-slate-600 dark:text-slate-400">{item.aiOffer.productName} by {item.aiOffer.provider}</p>
                        </div>
                        <StatusBadge status={item.listing.verificationStatus} />
                      </div>
                      <p className="text-xs font-bold text-slate-600 dark:text-slate-300">Expires: {formatDate(item.aiOffer.expiresAt)}</p>
                      <div className="flex justify-end gap-2">
                        <button type="button" onClick={() => setEditor({ kind: 'ai_offer', record: item })} className="btn-sharetopus-secondary px-3 py-2 text-xs font-extrabold"><Pencil className="h-4 w-4" /> Edit</button>
                        <button type="button" onClick={() => setDeleteTarget({ kind: 'ai_offer', id: item.listing.id, title: item.listing.title })} className="rounded-xl border-[1.5px] border-[#1C1B18] px-3 py-2 text-xs font-extrabold text-[#D23B14]"><Trash2 className="inline h-4 w-4" /> Delete</button>
                      </div>
                    </article>
                  ))}
            </div>
          </>
        )}
      </section>

      {editor && (
        <CatalogueEditorModal
          kind={editor.kind}
          hackathon={editor.kind === 'hackathon' ? editor.record : undefined}
          aiOffer={editor.kind === 'ai_offer' ? editor.record : undefined}
          busy={editorBusy}
          error={editorError}
          onClose={closeEditor}
          onSaveHackathon={saveHackathon}
          onSaveAIOffer={saveAIOffer}
        />
      )}

      {deleteTarget && (
        <DeleteConfirmModal
          target={deleteTarget}
          busy={deleteBusy}
          error={deleteError}
          onCancel={() => {
            if (deleteBusy) return;
            setDeleteTarget(null);
            setDeleteError(null);
          }}
          onConfirm={() => void confirmDelete()}
        />
      )}
    </div>
  );
};
