export type Item = {
  id: number;
  name: string;
  sku: string;
  price: number;
  quantity: number;
};

export type NewItem = {
  name: string;
  sku: string;
  price: number;
  quantity?: number;
};

export type ItemStats = {
  total: number;
  total_quantity: number;
  total_value: number;
  avg_price: number;
};

export type SearchResult = {
  query: string;
  count: number;
  items: Item[];
};

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class ApiClient {
  readonly baseUrl: string;

  constructor(baseUrl = "/api") {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, init);
    if (!response.ok) {
      throw new ApiError(response.status, `request failed with ${response.status}`);
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }

  listItems(): Promise<Item[]> {
    return this.request<Item[]>("/items");
  }

  getItem(id: number): Promise<Item> {
    return this.request<Item>(`/items/${id}`);
  }

  createItem(input: NewItem): Promise<Item> {
    return this.request<Item>("/items", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    });
  }

  deleteItem(id: number): Promise<void> {
    return this.request<void>(`/items/${id}`, { method: "DELETE" });
  }

  stats(): Promise<ItemStats> {
    return this.request<ItemStats>("/stats");
  }

  search(query: string): Promise<SearchResult> {
    return this.request<SearchResult>(`/search?q=${encodeURIComponent(query)}`);
  }
}

export function createApiClient(baseUrl?: string): ApiClient {
  return new ApiClient(baseUrl);
}
