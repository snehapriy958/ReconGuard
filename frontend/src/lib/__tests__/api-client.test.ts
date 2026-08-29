import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { ApiError } from "../api-client";
import { useApi } from "../use-api";

describe("ApiError", () => {
  it("carries an HTTP status code", () => {
    const err = new ApiError("not found", 404);
    expect(err.status).toBe(404);
    expect(err.message).toBe("not found");
    expect(err.name).toBe("ApiError");
  });
});

describe("useApi", () => {
  it("starts in loading state", () => {
    const { result } = renderHook(() =>
      useApi(() => new Promise(() => {}), [])
    );
    expect(result.current.status).toBe("loading");
  });

  it("transitions to success with real fetched data, not a placeholder", async () => {
    const fakeData = { batches: [{ batch_id: "BATCH-123", status: "COMPLETED" }] };
    const { result } = renderHook(() =>
      useApi(() => Promise.resolve(fakeData), [])
    );
    await waitFor(() => expect(result.current.status).toBe("success"));
    if (result.current.status === "success") {
      expect(result.current.data).toEqual(fakeData);
    }
  });

  it("transitions to error state when the fetcher rejects", async () => {
    const { result } = renderHook(() =>
      useApi(() => Promise.reject(new ApiError("boom", 500)), [])
    );
    await waitFor(() => expect(result.current.status).toBe("error"));
    if (result.current.status === "error") {
      expect(result.current.error.message).toBe("boom");
    }
  });

  it("refetch() triggers a new fetch call", async () => {
    const { act } = await import("@testing-library/react");
    const fetcher = vi.fn().mockResolvedValue({ ok: true });
    const { result } = renderHook(() => useApi(fetcher, []));
    await waitFor(() => expect(result.current.status).toBe("success"));
    expect(fetcher).toHaveBeenCalledTimes(1);
    act(() => {
      result.current.refetch();
    });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  });
});

describe("api-client request()", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("throws ApiError with status 0 on network failure, distinct from HTTP errors", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("network down"));
    const { listBatches } = await import("../api-client");
    await expect(listBatches()).rejects.toMatchObject({ status: 0 });
  });

  it("throws ApiError with the real HTTP status on a non-ok response", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: async () => ({ detail: "Batch not found" }),
    });
    const { getBatch } = await import("../api-client");
    await expect(getBatch("BATCH-doesnotexist")).rejects.toMatchObject({
      status: 404,
      message: "Batch not found",
    });
  });

  it("returns typed JSON on success without transformation", async () => {
    const payload = { batches: [] };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => payload,
    });
    const { listBatches } = await import("../api-client");
    const result = await listBatches();
    expect(result).toEqual(payload);
  });
});
