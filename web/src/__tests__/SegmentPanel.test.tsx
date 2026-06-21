import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SegmentPanel } from "../components/SegmentPanel";
import type { GeoFeature } from "../types/api";

const sampleFeature: GeoFeature = {
  type: "Feature",
  geometry: {
    type: "Polygon",
    coordinates: [
      [
        [0, 0],
        [1, 0],
        [1, 1],
        [0, 1],
        [0, 0],
      ],
    ],
  },
  properties: {
    object_id: 42,
    cover_type: "conifer",
    canopy_closure_class: "moderate",
    confidence: 0.72,
    area_m2: 12500,
    perimeter_m: 450,
    compactness: 0.81,
    manual_override: false,
  },
};

describe("SegmentPanel", () => {
  it("shows placeholder when no segment is selected", () => {
    render(
      <SegmentPanel feature={null} analystId="jsmith" onSubmitOverride={vi.fn()} />,
    );
    expect(screen.getByTestId("segment-panel")).toHaveTextContent(
      "Click a stand polygon",
    );
  });

  it("displays segment attributes when a feature is selected", () => {
    render(
      <SegmentPanel
        feature={sampleFeature}
        analystId="jsmith"
        onSubmitOverride={vi.fn()}
      />,
    );
    expect(screen.getByTestId("segment-cover-type")).toHaveTextContent("conifer");
    expect(screen.getByTestId("segment-confidence")).toHaveTextContent("72.0%");
    expect(screen.getByText("Stand #42")).toBeInTheDocument();
  });

  it("submits override with selected values", async () => {
    const user = userEvent.setup();
    const onSubmitOverride = vi.fn().mockResolvedValue(undefined);

    render(
      <SegmentPanel
        feature={sampleFeature}
        analystId="jsmith"
        onSubmitOverride={onSubmitOverride}
      />,
    );

    await user.selectOptions(screen.getByTestId("override-cover-select"), "deciduous");
    await user.selectOptions(screen.getByTestId("override-canopy-select"), "dense");
    await user.type(screen.getByTestId("override-reason"), "Visible hardwood crown");
    await user.click(screen.getByTestId("override-submit"));

    await waitFor(() => {
      expect(onSubmitOverride).toHaveBeenCalledWith(
        42,
        "deciduous",
        "dense",
        "Visible hardwood crown",
      );
    });

    expect(screen.getByTestId("override-message")).toHaveTextContent(
      "logged for future model training",
    );
  });
});
