// Stub: the plan's task T5 replaces this file with the real API client.
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
    throw new Error("not implemented");
  }

  listItems(): Promise<Item[]> {
    throw new Error("not implemented");
  }

  getItem(id: number): Promise<Item> {
    throw new Error("not implemented");
  }

  createItem(input: NewItem): Promise<Item> {
    throw new Error("not implemented");
  }

  deleteItem(id: number): Promise<void> {
    throw new Error("not implemented");
  }

  stats(): Promise<ItemStats> {
    throw new Error("not implemented");
  }

  search(query: string): Promise<SearchResult> {
    throw new Error("not implemented");
  }
}

export function createApiClient(baseUrl?: string): ApiClient {
  throw new Error("not implemented");
}
