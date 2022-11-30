(usage-map)=
# Making .map and .map.nc files

`.map` (*m*odel *a p*riori) files are a condensed file format that stores the a priori VMR profiles used by GGG.
These files aren't actually read by GGG, but are used to distribute the key a priori profiles to users who do
not want the full complexity of the `.vmr` or `.mav` files. Traditionally, these are generated during GGG post-processing
from the `.mav` file, but ginput can generate them directly.