import Link from "next/link";
import { products } from "../lib/products";

export default function HomePage() {
  return (
    <main className="container">
      <h1>Brick Drop</h1>
      <p>Official Lego sets, shipped fast — shop today's best deals before they're gone.</p>
      <div className="product-grid">
        {products.map((product) => (
          <div className="product-card" key={product.slug}>
            <img src={product.image} alt={product.name} width={300} height={300} />
            <h2>{product.name}</h2>
            <p>${product.price.toFixed(2)}</p>
            <Link href={`/product/${product.slug}`} className="cta">
              View set
            </Link>
          </div>
        ))}
      </div>
    </main>
  );
}
