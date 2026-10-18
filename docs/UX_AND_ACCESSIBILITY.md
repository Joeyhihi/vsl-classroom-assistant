# UX & Accessibility

**Target:** WCAG 2.2 AA. The UI is in Vietnamese first. The primary users are Deaf and hard-of-hearing adults, many of whom read Vietnamese as a **second language**.

## Principles

1. **Never rely on sound alone.** Every status uses text, an icon, and colour together (colour is never the only signal).
2. **Big, calm, readable.** Body text ≥18 px, prediction text ≥32 px, large display ≥96 px. High contrast (≥4.5:1, ≥7:1 for predictions). No flashing. Respects `prefers-reduced-motion`.
3. **Confirm before speaking.** Nothing is spoken automatically.
4. **No timeouts** on candidates or dialogs (WCAG 2.2.1).
5. **Keyboard first:** visible focus ring, logical tab order, shortcuts that don't fire while typing in a text field.
6. **Honest UI:** it states that it recognises a closed list of signs, not translation. The MOCK and experimental-model badges are always visible when they apply.

## Screens and views

| View | Contents | Phase |
|---|---|---|
| **CommunicationView** (main) | Camera preview (mirrored) with optional landmark overlay; status bar; Start/Stop; prediction card; confirm bar; transcript panel; manual text box; Speak button; connection banner | P2–P3 |
| SettingsView | Camera selector; voice selector (local vi-VN voices only) plus a test button; auto-speak (off); overlay on/off; extraction level (L1/L2/L3) with explanation; "delete local data" | P2 |
| PrivacyView | Plain-language notice: what runs where, what is never stored, how to delete | P2 |
| RecorderView | Behind `VITE_ENABLE_RECORDER`; consent ID field; red recording banner; prompts and countdown | P3 / P4 |
| SignGuideView | Supported signs with icons and consented reference clips or illustrations | P6 |
| LargeDisplayView | Last confirmed message full-screen for the teacher | P6 |
| Subtitle panel | Push-to-talk button (held), "Đang nghe" (listening) indicator, subtitle segments | P7 |

## Recognition states (visual design)

| State | Text (vi) | Icon | Colour token |
|---|---|---|---|
| idle | "Nhấn Bắt đầu để ký" (press Start to sign) | play | neutral |
| requesting_camera | "Đang xin quyền camera…" (requesting camera permission) | camera | info |
| camera_denied | "Chưa cho phép camera" (camera not allowed) + guide | camera-off | danger |
| loading_extractor | "Đang tải bộ nhận dạng…" (loading recogniser) | spinner | info |
| waiting_for_hands | "Đưa tay vào khung hình" (bring your hands into the frame) | hand | warning |
| ready | "Sẵn sàng" (ready) | check | success |
| signing | "Đang ký…" (signing) | wave | active |
| processing | "Đang xử lý…" (processing) | spinner | info |
| candidate (confident) | the text_vi + icon | — | primary |
| candidate (uncertain) | "Bạn muốn nói gì?" (what did you mean?) + 3 options | question | warning |
| rejected | "Không nhận ra — hãy ký lại" (not recognised, please sign again) | x | neutral |
| paused | "Tạm dừng" (paused) | pause | neutral |
| disconnected | "Mất kết nối máy chủ" (lost connection to server) | plug | danger |
| speaking | "Đang phát" (playing), with an animated bar or static under reduced motion | speaker | active |

Status changes are announced through an `aria-live="polite"` region. A `rejected` result or an error uses `assertive` only for blocking errors.

## Interaction details

- **Keyboard shortcuts** (inactive while a text input has focus):

  | Key | Action |
  |---|---|
  | `Enter` | Confirm |
  | `Esc` | Dismiss |
  | `1`–`3` | Pick an alternative |
  | `S` | Speak the last entry |

  Start/Stop is a large button with an `accesskey`.
- **Candidate policy:** one pending candidate. A new prediction replaces it, and the old one goes to a "Bỏ qua" (skipped) list for 3 entries.
- **Permission flow:**
  1. Explain why the camera is needed, before the browser prompt appears.
  2. Show the browser prompt.
  3. If denied, show Chrome-specific steps to re-enable it, with a Retry button.

  Manual text stays usable the whole time.
- **Hands-busy confirmation (open question):** the signer has to move from signing to pressing a button. Alternatives to explore with Deaf users: a large on-screen button reachable with an elbow or forearm, the space bar, or a foot pedal (a USB keyboard key). P6 UX sessions decide.
- **Literacy:** every message unit shows an icon. The guide uses reference clips. Experts approve short, simple `text_vi`.
- **Bystanders:** a persistent "Camera đang bật" (camera on) indicator. The overlay shows who is being tracked, with positioning tips.

## Phase 2 implementation notes

- Navigation is three buttons with `aria-current="page"`: Giao tiếp (communicate), Cài đặt (settings), Quyền riêng tư (privacy). Camera state lives above the views, so the camera keeps running when switching views.
- The camera panel explains why the camera is needed before the browser prompt. Each failure state (denied, unavailable, in use, insecure) has its own message, recovery step and Retry button, rendered as `role="alert"`.
- The transcript is a `role="log"` region containing an ordered list. Each entry shows speaker, source, time and a Speak button; spoken entries get an "Đã đọc" (spoken) badge.
- Manual text: Enter sends, Shift+Enter adds a new line (IME composition is respected), up to 500 characters, NFC-normalised.
- While speech is playing, a "Đang phát" (playing) indicator with a Stop button is shown. If there is no local vi-VN voice, a notice explains how to install one on macOS and on Windows.
- Settings shows a voice diagnostics list (this is how voice availability is recorded per machine) and a two-step "delete local data" action.

## Accessibility checks

- Automated: `vitest-axe` on every component and view (P1+); Playwright + axe on the main flows (P2+).
- Manual (P8): keyboard-only run-through, 200% zoom, high-contrast mode, screen-reader smoke test, and **sessions with Deaf users** covering segmentation comfort, confirmation, sign guide, and the large display.
