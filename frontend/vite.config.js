import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 개발 시 /api 요청을 로컬 FastAPI(uvicorn)로 프록시한다.
// 배포 시에는 CloudFront가 같은 도메인의 /api/*를 Lambda로 라우팅한다(Step 7).
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
