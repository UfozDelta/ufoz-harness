import Link from "next/link";
import { notFound } from "next/navigation";
import { products, getProduct } from "../../../lib/products";
import AddToCartButton from "../../../components/AddToCartButton";

export function generateStaticParams() {
  return products.map((p) => ({ slug: p.slug }));
}

export default function ProductPage({ params }: { params: { slug: string } }) {
  const product = getProduct(params.slug);
  if (!product) notFound();

  return (
    <main className="container">
      <img src={product.image} alt={product.name} width={400} height={400} />
      <h1>{product.name}</h1>
      <p>${product.price.toFixed(2)}</p>
      <p>{product.description}</p>
      <AddToCartButton product={product} />
      <p>
        <Link href="/">Back to catalog</Link>
      </p>
    </main>
  );
}
