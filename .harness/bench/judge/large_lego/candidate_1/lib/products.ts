export type Product = { slug: string; name: string; price: number; image: string; description: string };

export const products: Product[] = [
  {
    slug: "millennium-falcon",
    name: "Millennium Falcon",
    price: 849.99,
    image: "/images/placeholder.svg",
    description: "Iconic Star Wars starship model with detailed interior and rotating turrets.",
  },
  {
    slug: "hogwarts-castle",
    name: "Hogwarts Castle",
    price: 469.99,
    image: "/images/placeholder.svg",
    description: "Sprawling castle build featuring towers, classrooms, and the Great Hall.",
  },
  {
    slug: "city-police-station",
    name: "City Police Station",
    price: 109.99,
    image: "/images/placeholder.svg",
    description: "Fully equipped police headquarters with jail cell and patrol vehicles.",
  },
  {
    slug: "technic-bugatti",
    name: "Technic Bugatti Chiron",
    price: 379.99,
    image: "/images/placeholder.svg",
    description: "Highly detailed supercar replica with working steering and gearbox.",
  },
  {
    slug: "botanical-orchid",
    name: "Botanical Orchid",
    price: 49.99,
    image: "/images/placeholder.svg",
    description: "Elegant display flower that never needs watering or sunlight.",
  },
  {
    slug: "ninjago-dragon",
    name: "Ninjago Ice Dragon",
    price: 19.99,
    image: "/images/placeholder.svg",
    description: "Posable ice dragon figure with articulated wings and frosty details.",
  },
];

export function getProduct(slug: string): Product | undefined {
  return products.find((p) => p.slug === slug);
}
