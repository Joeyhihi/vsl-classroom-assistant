// All user-facing strings (Vietnamese first). Error codes map to messages here.

export const vi = {
  appTitle: "Trợ lý lớp học VSL",
  appTagline: "Nhận dạng một danh sách nhỏ ký hiệu VSL — không phải phiên dịch.",
  phaseNotice:
    "Phiên bản nền tảng (Giai đoạn 1): chưa có nhận dạng ký hiệu, camera hay giọng nói.",
  backend: {
    heading: "Trạng thái máy chủ",
    checking: "Đang kiểm tra kết nối…",
    online: "Đã kết nối máy chủ",
    degraded: "Máy chủ hoạt động nhưng thiếu một số chức năng",
    offline: "Mất kết nối máy chủ",
    offlineHelp: "Hãy chạy: uv run python scripts/run_backend.py",
    incompatible: "Phiên bản máy chủ không khớp với ứng dụng",
  },
  components: {
    sign_model: "Nhận dạng ký hiệu",
    stt: "Giọng nói → chữ",
    tts: "Đọc thành tiếng (máy chủ)",
  },
  componentStatus: {
    ready: "Sẵn sàng",
    loading: "Đang tải",
    unavailable: "Không khả dụng",
    disabled: "Tắt",
    mock: "Mô phỏng",
  },
  mockBadge: "MOCK",
  mockBadgeLabel: "Chế độ mô phỏng: kết quả là kịch bản, không phải nhận dạng thật",
} as const;

export const errorMessages: Record<string, string> = {
  VALIDATION_ERROR: "Dữ liệu gửi lên không hợp lệ.",
  PAYLOAD_TOO_LARGE: "Dữ liệu quá lớn.",
  RATE_LIMITED: "Gửi quá nhanh, vui lòng thử lại.",
  ORIGIN_FORBIDDEN: "Ứng dụng không được phép kết nối máy chủ.",
  NOT_FOUND: "Không tìm thấy.",
  PROTOCOL_MISMATCH: "Phiên bản giao thức không khớp — hãy tải lại trang.",
  FEATURE_SPEC_MISMATCH: "Cấu hình nhận dạng không khớp — hãy tải lại trang.",
  EXTRACTION_UNAVAILABLE: "Xử lý trên máy chủ không khả dụng.",
  MODEL_UNAVAILABLE: "Nhận dạng ký hiệu không khả dụng.",
  RESOURCE_EXHAUSTED: "Không đủ bộ nhớ.",
  STT_UNAVAILABLE: "Chuyển giọng nói thành chữ không khả dụng.",
  INTERNAL: "Lỗi máy chủ. Vui lòng thử lại.",
};
