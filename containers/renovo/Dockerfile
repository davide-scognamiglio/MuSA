# ReNOVo with the prediction-reinsertion fix (see Renovo_implementation.py header).
#
# Upstream 1.1.0/1.1.1 ship an identical, broken Renovo_implementation.py: it realigns predictions
# onto the full input by walking a counter, which crashes on adjacent dropped rows and silently
# shifts PL_score around isolated ones. Everything else in the image is untouched.
#
# Build (from this directory):
#   docker build -t dsbioinfo/renovo:1.1.2 .
FROM dsbioinfo/renovo:1.1.0

COPY Renovo_implementation.py /software/renovo/Scripts/Renovo_implementation.py
