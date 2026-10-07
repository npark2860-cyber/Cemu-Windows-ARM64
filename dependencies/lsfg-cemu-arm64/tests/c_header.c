#include "lsfg_cemu.h"
#include <string.h>
int main(void) {
  LsfgCemu *module = NULL;
  LsfgCemuError error = {0};
  if (lsfg_cemu_create(NULL, &module, &error) != LSFG_CEMU_INVALID_ARGUMENT)
    return 1;
  if (module || error.status != LSFG_CEMU_INVALID_ARGUMENT ||
      error.vk_result_valid)
    return 2;
  if (strcmp(lsfg_cemu_status_string(LSFG_CEMU_TIMEOUT), "TIMEOUT") != 0)
    return 3;
  if (lsfg_cemu_destroy(&module, &error) != LSFG_CEMU_OK)
    return 4;
  if (lsfg_cemu_prepare(NULL, &error) != LSFG_CEMU_INVALID_ARGUMENT ||
      lsfg_cemu_prepare_context(NULL, &error) != LSFG_CEMU_INVALID_ARGUMENT ||
      lsfg_cemu_generate_step(NULL, NULL, &error) != LSFG_CEMU_INVALID_ARGUMENT)
    return 5;
  LsfgCemuResourceStats resources = {sizeof(LsfgCemuResourceStats), 0, 0};
  if (lsfg_cemu_get_resource_stats(NULL, &resources, &error) != LSFG_CEMU_INVALID_ARGUMENT ||
      strcmp(lsfg_cemu_status_string(LSFG_CEMU_WARMING), "WARMING") != 0)
    return 6;
  LsfgCemuTimingStats timing = {0};
  timing.struct_size = sizeof(timing);
  if (lsfg_cemu_get_timing_stats(NULL, &timing, &error) != LSFG_CEMU_INVALID_ARGUMENT)
    return 7;
  LsfgCemuContextTuning tuning = {sizeof(LsfgCemuContextTuning), VK_TRUE, 75};
  if (lsfg_cemu_set_context_tuning(NULL, &tuning, &error) != LSFG_CEMU_INVALID_ARGUMENT)
    return 8;
  return 0;
}
