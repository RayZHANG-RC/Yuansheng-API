# Question Configuration - Unified CSV-Based LLM Management

This directory contains the consolidated question configuration files with a unified CSV-based approach for managing LLM configurations across different GPT versions.

## Structure

### Unified CSV Configuration File

**unified_llm_config.csv**: Contains per-question LLM configurations for both GPT-4.1-NANO and GPT-5-NANO model sets
- Columns: 
  - `question_id`: Unique identifier for each question
  - `config_set`: Default configuration set to use ('gpt-4.1' or 'gpt-5')
  - `gpt41_quantitative_model`: GPT-4.1 model for quantitative analysis
  - `gpt41_quantitative_temperature`: GPT-4.1 temperature for quantitative analysis
  - `gpt41_qualitative_model`: GPT-4.1 model for qualitative analysis  
  - `gpt41_qualitative_temperature`: GPT-4.1 temperature for qualitative analysis
  - `gpt5_quantitative_model`: GPT-5 model for quantitative analysis
  - `gpt5_qualitative_model`: GPT-5 model for qualitative analysis
  - `description`: Description of the LLM configuration

This unified approach supports both GPT-4.1-NANO and GPT-5-NANO configurations with easy switching between them.

### Question Files

- All question files (*.jsonc) now use the unified CSV configuration system
- The `llm_config` section is loaded dynamically from the CSV file based on the active model set
- This eliminates the need for duplicate question files between GPT versions

## Model Switching

The system supports switching between two model configurations:

1. **GPT-4.1-NANO Configuration**:
   - Quantitative stage: `gpt-4.1-nano` with `temperature=0.1`
   - Qualitative stage: `gpt-4.1-mini` with `temperature=0.3`

2. **GPT-5-NANO Configuration**:
   - Quantitative stage: `gpt-5-nano` (simplified parameter set)
   - Qualitative stage: `gpt-5-nano` (simplified parameter set)

### How to Switch Models

In `template_withoutDB_classed.py`, modify the `GLOBAL_MODEL_SET` variable:

```python
# Options: 'gpt-4.1', 'gpt-5', or None
GLOBAL_MODEL_SET = 'gpt-4.1'  # Use GPT-4.1 for all questions
GLOBAL_MODEL_SET = 'gpt-5'    # Use GPT-5 for all questions  
GLOBAL_MODEL_SET = None       # Use CSV default for each question
```

## Migration from Separate GPT Directories

This approach consolidates the previous structure:
- `data_prompt_engineering/api_b2c/question config GPT-4.1_legacy/` 
- `data_prompt_engineering/api_b2c/question config GPT-5_legacy/`

Into a single directory with unified CSV-based configuration management.

## Benefits

1. **Reduced Duplication**: No more duplicate question files for different GPT versions
2. **Cleaner Codebase**: Single source of truth for question configurations
3. **Per-Question Customization**: Easy to customize LLM parameters for each individual question
4. **Easy Model Switching**: Simple global switch between GPT-4.1-NANO and GPT-5-NANO
5. **Stage-Specific Control**: Different LLM configurations for quantitative vs qualitative stages
6. **Centralized Management**: All LLM configurations managed in one unified CSV file
7. **Easier Maintenance**: Updates to LLM parameters only need to be made in the unified CSV file

## Usage

The calling code automatically loads the appropriate configuration based on the `GLOBAL_MODEL_SET` setting:

```python
from template_withoutDB_classed import load_unified_llm_config, get_llm_config

# Load configuration with model switching
config_dict = load_unified_llm_config(model_set='gpt-4.1')  # Force GPT-4.1
config_dict = load_unified_llm_config(model_set='gpt-5')    # Force GPT-5
config_dict = load_unified_llm_config()                     # Use CSV defaults

# Get LLM config for a specific question and stage
quant_config = get_llm_config("REL01_Q001", "quantitative", config_dict)
qual_config = get_llm_config("REL01_Q001", "qualitative", config_dict)

print(f"Quantitative model: {quant_config.get('model')}")
print(f"Qualitative model: {qual_config.get('model')}")
```

## Configuration Examples

### GPT-4.1-NANO Configuration
```python
{
  'quantitative_stage': {
    'model': 'gpt-4.1-nano',
    'temperature': 0.1
  },
  'qualitative_stage': {
    'model': 'gpt-4.1-mini', 
    'temperature': 0.3
  }
}
```

### GPT-5-NANO Configuration
```python
{
  'quantitative_stage': {
    'model': 'gpt-5-nano'
  },
  'qualitative_stage': {
    'model': 'gpt-5-nano'
  }
}
```