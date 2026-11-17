
import type { DSSService } from '../../types/dss'

import { mockDssService } from './mockDssService'

/**
 * CoLogi Decision Support Service
 *
 * Chế độ hiện tại: DEMO / MOCK
 *
 * Khi backend F1-F5 sẵn sàng:
 * - Viết implementation kết nối API thật.
 * - Giữ nguyên DSSService interface nếu có thể.
 * - Chuyển implementation tại đây.
 *
 * Không xem dữ liệu mock là kết quả DSS thực tế.
 */

export const DSS_DATA_MODE = 'MOCK' as const

export const dssService: DSSService = mockDssService