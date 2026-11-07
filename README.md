# video-edit-skills

Skillovi za Claude Code za montažu talking-head videa (rilovi za Instagram/TikTok).
Snimiš sve u jednom kadru, sa greškama i dublovima, a Claude iseče video po scenariju,
doda zum, titlove, B-roll, close-up snimke, naslov iza glave, muziku i grafike.

*Claude Code skills for editing talking-head reels: cut a single raw take by the script,
then zoom, captions, B-roll, close-ups, a title behind the head, music and chapter cards.*

## Instalacija

U Claude Code-u:

```
/plugin marketplace add Istok-Media-Tool/video-edit-skills
/plugin install video-edit@video-edit-skills
```

Repo je javan, pa ti ne treba nikakav pristup ni prijava na GitHub.

## Automatsko ažuriranje (uradi jednom)

Skillovi se redovno dopunjuju. Da bi ti Claude Code sam povlačio nove verzije:

1. U Claude Code-u ukucaj `/plugin`
2. Marketplaces → `video-edit-skills` → **Enable auto-update**

Posle toga se nova verzija preuzima pri svakom pokretanju Claude Code-a.
Ručno ažuriranje, kad god hoćeš: `/plugin marketplace update video-edit-skills`

## Šta je unutra

| Skill | Šta radi |
|---|---|
| `basic` | seče sirov snimak po scenariju (Whisper + detekcija tišine), bira dublove, proverava svaki render (`check_video.py`) |
| `plan-editor` | interaktivni editor u browseru: zum po rečima, ispravka titlova, B-roll, close-up klizači, dublovi jedan pored drugog, naslov |
| `zoom` | dinamički zum, centriran na lice, bez sečenja predmeta koje pokazuješ |
| `subtitle` | titlovi (ASS + libass), prelomi gde se prirodno pravi pauza |
| `title-behind` | veliki naslov iza glave (osoba isečena ispred teksta) |
| `music` | muzika ispod glasa, posebna pesma po delu videa, TV promena kanala na prelazima |
| `chapter-cards` | kartice za delove videa, jedan šablon (neon stil 80-ih) sa vremenskom lentom |

## Šta treba instalirati

- macOS (praćenje lica koristi Apple Vision)
- `ffmpeg` i `ffmpeg-full` (titlovi): `brew install ffmpeg ffmpeg-full`
- [Whisper](https://github.com/openai/whisper): `pip install -U openai-whisper`
- Python 3 sa `numpy`
- Za naslov iza glave i kartice: HyperFrames skillovi i CLI (`npx hyperframes`), instaliraju se posebno

## Kako se koristi

Samo pričaj sa Claude-om, npr.:

- „Snimio sam video u jednom komadu, iseci ga po scenariju” (+ video i scenario)
- „Otvori editor”, „dodaj zum”, „stavi titlove”, „ubaci B-roll”
- „Stavi naslov MODA iza glave”
- „Dodaj muziku, posebnu za svaki deo”
- „Napravi kartice za svaki period”
