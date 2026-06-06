/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 允许大文件上传（单细胞文件可能较大）
  experimental: {
    serverActions: {
      bodySizeLimit: "200mb",
    },
  },
};

module.exports = nextConfig;
