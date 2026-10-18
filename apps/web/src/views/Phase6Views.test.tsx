import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import axe from "axe-core";
import { describe, expect, it, vi as vitest } from "vitest";

import { FeedbackControls } from "../components/transcript/FeedbackControls";
import { createManualEntry, createSignEntry } from "../features/transcript/transcriptStore";
import { vi } from "../i18n/vi";
import { LargeDisplayView } from "./LargeDisplayView";
import { SignGuideView } from "./SignGuideView";

const VOCAB = [
  { gloss_id: "DEV_01", text_vi: "Xin chào", icon: "wave" },
  { gloss_id: "DEV_02", text_vi: "Cảm ơn", icon: "thanks" },
];

async function expectNoAxeViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  expect(results.violations).toEqual([]);
}

describe("SignGuideView", () => {
  it("lists every sign with its icon", async () => {
    const { container } = render(
      <SignGuideView vocabulary={{ kind: "ready", version: "dev-1", entries: VOCAB }} developerOnly />,
    );
    expect(screen.getByText("Xin chào")).toBeInTheDocument();
    expect(screen.getByText("👋")).toBeInTheDocument();
    expect(screen.getByText(vi.guide.count(2, "dev-1"))).toBeInTheDocument();
    expect(screen.getByText(vi.guide.devNotice)).toBeInTheDocument();
    await expectNoAxeViolations(container);
  });

  it("explains when there is no model", () => {
    render(<SignGuideView vocabulary={{ kind: "unavailable" }} developerOnly={false} />);
    expect(screen.getByText(vi.guide.unavailable)).toBeInTheDocument();
  });
});

describe("LargeDisplayView", () => {
  it("shows the last confirmed message", async () => {
    const entries = [
      createManualEntry("Câu đầu", "teacher"),
      createSignEntry({ gloss_id: "DEV_01", text_vi: "Xin chào", score: 0.9, icon: "wave" }),
    ];
    const { container } = render(<LargeDisplayView entries={entries} />);
    const message = screen.getByTestId("large-display-message");
    expect(message).toHaveTextContent("Xin chào");
    expect(message).not.toHaveTextContent("Câu đầu");
    await expectNoAxeViolations(container);
  });

  it("has an empty state and survives a missing fullscreen API", () => {
    render(<LargeDisplayView entries={[]} />);
    expect(screen.getByText(vi.largeDisplay.empty)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: vi.largeDisplay.fullscreen }));
    expect(screen.getByText(vi.largeDisplay.fullscreenFailed)).toBeInTheDocument();
  });
});

describe("FeedbackControls", () => {
  const entry = createSignEntry({ gloss_id: "DEV_01", text_vi: "Xin chào", score: 0.9 }, new Date(), {
    session_id: "s",
    prediction_id: "p",
    model_id: "m",
  });

  it("sends a correct verdict in one click", async () => {
    const onSend = vitest.fn(() => Promise.resolve());
    render(<FeedbackControls entry={entry} vocabulary={VOCAB} onSend={onSend} />);
    fireEvent.click(screen.getByRole("button", { name: /Đúng/ }));
    await waitFor(() => expect(onSend).toHaveBeenCalledWith(entry, "correct", null));
  });

  it("asks which sign was meant, offering the other signs only", async () => {
    const onSend = vitest.fn(() => Promise.resolve());
    render(<FeedbackControls entry={entry} vocabulary={VOCAB} onSend={onSend} />);
    fireEvent.click(screen.getByRole("button", { name: /Sai/ }));
    const select = screen.getByLabelText(vi.feedback.expectedLabel);
    expect(screen.queryByRole("option", { name: "Xin chào" })).toBeNull();
    fireEvent.change(select, { target: { value: "DEV_02" } });
    fireEvent.click(screen.getByRole("button", { name: vi.feedback.send }));
    await waitFor(() => expect(onSend).toHaveBeenCalledWith(entry, "incorrect", "DEV_02"));
  });

  it("shows an error when sending fails, and a thank-you once recorded", async () => {
    const onSend = vitest.fn(() => Promise.reject(new Error("down")));
    const { rerender } = render(<FeedbackControls entry={entry} vocabulary={VOCAB} onSend={onSend} />);
    fireEvent.click(screen.getByRole("button", { name: /Không chắc/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(vi.feedback.failed);

    rerender(<FeedbackControls entry={{ ...entry, feedback: "unsure" }} vocabulary={VOCAB} onSend={onSend} />);
    expect(screen.getByText(vi.feedback.thanks(vi.feedback.verdicts.unsure))).toBeInTheDocument();
  });
});
