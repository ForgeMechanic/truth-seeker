# Parser architecture

Input validation belongs to the Parser component. Storage is responsible for
persisting values and must not own input-validation behavior. Its public API must
not expose validation methods.
