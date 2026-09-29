import Link from "next/link";
import { products } from "../lib/products";

export default function HomePage() {
  return (
    <main>
      <h1>Brick Drop — Lego Sets</h1>
      <p>Build your next adventure — shop the most-loved Lego sets.</p>
      <div className="product-grid">
        {products.map((product) => (
          <article key={product.slug} className="product-card">
            <img src={product.image} alt={product.name} width={300} height={300} />
            <h2>{product.name}</h2>
            <p>${product.price.toFixed(2)}</p>
            <Link href={`/product/${product.slug}`}>View set</Link>
          </article>
        ))}
      </div>
    </main>
  );
}
