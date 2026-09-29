export type Product = { slug: string; name: string; price: number; image: string; description: string };

export const products: Product[] = [
  {
    slug: "millennium-falcon",
    name: "Millennium Falcon",
    price: 849.99,
    image: "/images/placeholder.svg",
    description: "Build the iconic Millennium Falcon starship with detailed minifigures included.",
  },
  {
    slug: "hogwarts-castle",
    name: "Hogwarts Castle",
    price: 399.99,
    image: "/images/placeholder.svg",
    description: "Recreate the magical Hogwarts Castle with towers classrooms and hidden chambers.",
  },
  {
    slug: "city-police-station",
    name: "City Police Station",
    price: 99.99,
    image: "/images/placeholder.svg",
    description: "Patrol the bustling city streets with this detailed police station playset.",
  },
  {
    slug: "technic-bugatti",
    name: "Technic Bugatti Chiron",
    price: 349.99,
    image: "/images/placeholder.svg",
    description: "Engineer the stunning Bugatti Chiron supercar with working pistons and steering.",
  },
  {
    slug: "botanical-orchid",
    name: "Botanical Orchid",
    price: 49.99,
    image: "/images/placeholder.svg",
    description: "Display the elegant white and pink orchid flowers in a blue vase.",
  },
  {
    slug: "ninjago-dragon",
    name: "Ninjago Ice Dragon",
    price: 59.99,
    image: "/images/placeholder.svg",
    description: "Battle alongside the powerful Ninjago ice dragon with posable wings and tail.",
  },
];

export function getProduct(slug: string): Product | undefined {
  return products.find((p) => p.slug === slug);
}
