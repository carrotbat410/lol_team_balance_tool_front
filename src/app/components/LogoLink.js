'use client';
import Link from 'next/link';
import Image from 'next/image';

export default function LogoLink() {
  return (
    <Link href="/" className="logo" onClick={() => window.location.href = '/'}>
      <Image src="/logo.webp" alt="로고" width={120} height={20} />
    </Link>
  );
}
