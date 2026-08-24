"use client";

import { useState } from "react";
import { X, Plus, Trash2, ChevronDown, ChevronRight } from "lucide-react";
import ImageUpload from "@/components/shared/ImageUpload";

export interface EpisodeInput {
  id?: string;
  number: number;
  title: string;
  embedUrl: string;
  embedProvider?: string;
}

export interface SeasonInput {
  id?: string;
  number: number;
  title?: string;
  episodes: EpisodeInput[];
}

export interface SeriesFormValues {
  title: string;
  description?: string;
  thumbnailUrl: string;
  bannerUrl?: string;
  status: "DRAFT" | "PUBLISHED" | "ARCHIVED";
  genres: string[]; // Namen, kommasepariert im UI
  tags: string[]; // z.B. "Let's Play" — eigene Übersichtsseite pro Tag
  seasons: SeasonInput[];
}

interface Props {
  initialValues?: Partial<SeriesFormValues> & { seasons?: any[] };
  onClose: () => void;
  onSave: (values: SeriesFormValues) => Promise<void> | void;
}

function emptySeason(number: number): SeasonInput {
  return { number, title: "", episodes: [{ number: 1, title: "", embedUrl: "" }] };
}

export default function SeriesFormModal({ initialValues, onClose, onSave }: Props) {
  const [title, setTitle] = useState(initialValues?.title ?? "");
  const [description, setDescription] = useState(initialValues?.description ?? "");
  const [thumbnailUrl, setThumbnailUrl] = useState(initialValues?.thumbnailUrl ?? "");
  const [bannerUrl, setBannerUrl] = useState(initialValues?.bannerUrl ?? "");
  const [status, setStatus] = useState<SeriesFormValues["status"]>(
    (initialValues?.status as SeriesFormValues["status"]) ?? "DRAFT"
  );
  const [genresInput, setGenresInput] = useState(
    initialValues?.genres?.join(", ") ?? ""
  );
  const [tagsInput, setTagsInput] = useState(
    initialValues?.tags?.join(", ") ?? ""
  );
  const [seasons, setSeasons] = useState<SeasonInput[]>(
    (initialValues?.seasons as SeasonInput[]) ?? [emptySeason(1)]
  );
  const [openSeason, setOpenSeason] = useState<number>(0);
  const [saving, setSaving] = useState(false);

  function updateSeason(index: number, patch: Partial<SeasonInput>) {
    setSeasons((prev) => prev.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  }

  function updateEpisode(seasonIdx: number, epIdx: number, patch: Partial<EpisodeInput>) {
    setSeasons((prev) =>
      prev.map((s, i) =>
        i === seasonIdx
          ? {
              ...s,
              episodes: s.episodes.map((ep, j) => (j === epIdx ? { ...ep, ...patch } : ep)),
            }
          : s
      )
    );
  }

  function addSeason() {
    setSeasons((prev) => [...prev, emptySeason(prev.length + 1)]);
    setOpenSeason(seasons.length);
  }

  function removeSeason(index: number) {
    setSeasons((prev) => prev.filter((_, i) => i !== index));
  }

  function addEpisode(seasonIdx: number) {
    setSeasons((prev) =>
      prev.map((s, i) =>
        i === seasonIdx
          ? {
              ...s,
              episodes: [
                ...s.episodes,
                { number: s.episodes.length + 1, title: "", embedUrl: "" },
              ],
            }
          : s
      )
    );
  }

  function removeEpisode(seasonIdx: number, epIdx: number) {
    setSeasons((prev) =>
      prev.map((s, i) =>
        i === seasonIdx ? { ...s, episodes: s.episodes.filter((_, j) => j !== epIdx) } : s
      )
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave({
        title,
        description,
        thumbnailUrl,
        bannerUrl,
        status,
        genres: genresInput.split(",").map((g) => g.trim()).filter(Boolean),
        tags: tagsInput.split(",").map((t) => t.trim()).filter(Boolean),
        seasons,
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-white/10 bg-neutral-900 p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold">
            {initialValues ? "Serie bearbeiten" : "Neue Serie anlegen"}
          </h2>
          <button onClick={onClose} className="rounded-md p-1 text-neutral-400 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Basis-Metadaten */}
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="mb-1 block text-xs font-medium text-neutral-400">Titel</label>
              <input
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm outline-none focus:border-indigo-500"
              />
            </div>
            <div className="col-span-2">
              <label className="mb-1 block text-xs font-medium text-neutral-400">Beschreibung</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <ImageUpload
                bucket="thumbnails"
                pathPrefix="series"
                value={thumbnailUrl}
                onChange={setThumbnailUrl}
                label="Thumbnail"
                aspect="portrait"
              />
            </div>
            <div>
              <ImageUpload
                bucket="thumbnails"
                pathPrefix="series"
                value={bannerUrl}
                onChange={setBannerUrl}
                label="Banner (optional)"
                aspect="wide"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-neutral-400">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as SeriesFormValues["status"])}
                className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm outline-none focus:border-indigo-500"
              >
                <option value="DRAFT">Entwurf</option>
                <option value="PUBLISHED">Veröffentlicht</option>
                <option value="ARCHIVED">Archiviert</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-neutral-400">
                Genres (kommagetrennt)
              </label>
              <input
                value={genresInput}
                onChange={(e) => setGenresInput(e.target.value)}
                placeholder="Action, Fantasy, Isekai"
                className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-neutral-400">
                Tags (kommagetrennt, z.B. eigene Sammlungen)
              </label>
              <input
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder="Let's Play, Community-Favorit"
                className="w-full rounded-lg border border-white/10 bg-neutral-800 px-3 py-2 text-sm outline-none focus:border-indigo-500"
              />
            </div>
          </div>

          {/* Staffeln & Episoden */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <label className="text-xs font-medium text-neutral-400">Staffeln & Episoden</label>
              <button
                type="button"
                onClick={addSeason}
                className="flex items-center gap-1 text-xs font-medium text-indigo-400 hover:text-indigo-300"
              >
                <Plus className="h-3.5 w-3.5" /> Staffel hinzufügen
              </button>
            </div>

            <div className="space-y-2">
              {seasons.map((season, sIdx) => (
                <div key={sIdx} className="rounded-lg border border-white/10 bg-neutral-800/50">
                  <button
                    type="button"
                    onClick={() => setOpenSeason(openSeason === sIdx ? -1 : sIdx)}
                    className="flex w-full items-center justify-between px-3 py-2 text-sm"
                  >
                    <span className="flex items-center gap-2">
                      {openSeason === sIdx ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                      Staffel {season.number} · {season.episodes.length} Episode(n)
                    </span>
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        removeSeason(sIdx);
                      }}
                      className="rounded p-1 text-neutral-500 hover:bg-red-500/10 hover:text-red-400"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </span>
                  </button>

                  {openSeason === sIdx && (
                    <div className="space-y-3 border-t border-white/10 p-3">
                      <input
                        placeholder="Staffel-Titel (optional)"
                        value={season.title ?? ""}
                        onChange={(e) => updateSeason(sIdx, { title: e.target.value })}
                        className="w-full rounded-md border border-white/10 bg-neutral-900 px-2 py-1.5 text-xs outline-none focus:border-indigo-500"
                      />

                      {season.episodes.map((ep, eIdx) => (
                        <div
                          key={eIdx}
                          className="grid grid-cols-12 gap-2 rounded-md bg-neutral-900/60 p-2"
                        >
                          <input
                            type="number"
                            value={ep.number}
                            onChange={(e) =>
                              updateEpisode(sIdx, eIdx, { number: Number(e.target.value) })
                            }
                            className="col-span-1 rounded border border-white/10 bg-neutral-800 px-1 py-1 text-xs"
                          />
                          <input
                            placeholder="Episodentitel"
                            value={ep.title}
                            onChange={(e) => updateEpisode(sIdx, eIdx, { title: e.target.value })}
                            className="col-span-4 rounded border border-white/10 bg-neutral-800 px-2 py-1 text-xs"
                          />
                          <input
                            placeholder="Embed-URL / Iframe-Link des Hosters"
                            value={ep.embedUrl}
                            onChange={(e) =>
                              updateEpisode(sIdx, eIdx, { embedUrl: e.target.value })
                            }
                            className="col-span-5 rounded border border-white/10 bg-neutral-800 px-2 py-1 text-xs"
                          />
                          <input
                            placeholder="Anbieter"
                            value={ep.embedProvider ?? ""}
                            onChange={(e) =>
                              updateEpisode(sIdx, eIdx, { embedProvider: e.target.value })
                            }
                            className="col-span-1 rounded border border-white/10 bg-neutral-800 px-2 py-1 text-xs"
                          />
                          <button
                            type="button"
                            onClick={() => removeEpisode(sIdx, eIdx)}
                            className="col-span-1 flex items-center justify-center rounded text-neutral-500 hover:text-red-400"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}

                      <button
                        type="button"
                        onClick={() => addEpisode(sIdx)}
                        className="flex items-center gap-1 text-xs font-medium text-indigo-400 hover:text-indigo-300"
                      >
                        <Plus className="h-3.5 w-3.5" /> Episode hinzufügen
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm text-neutral-300 hover:bg-white/5"
            >
              Abbrechen
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {saving ? "Speichern…" : "Speichern"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
