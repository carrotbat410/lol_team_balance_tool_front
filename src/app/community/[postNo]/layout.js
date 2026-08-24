export async function generateMetadata({ params }) {
  const { postNo } = await params;

  return {
    alternates: {
      canonical: `/community/${postNo}`,
    },
  };
}

export default function CommunityDetailLayout({ children }) {
  return children;
}
