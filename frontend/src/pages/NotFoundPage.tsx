export function NotFoundPage() {
  return (
    <section className="not-found" aria-labelledby="not-found-title">
      <h1 id="not-found-title">Page not found</h1>
      <p>This link does not match a page or a property in your workspace.</p>
      <a className="btn btn-primary btn-md" href="#/">
        Go to Properties
      </a>
    </section>
  );
}
