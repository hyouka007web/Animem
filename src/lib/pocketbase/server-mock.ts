export const createAdminClient = async () => ({
  collection: () => ({
    getList: async () => ({ items: [] }),
    getFullList: async () => [],
    getOne: async () => ({}),
  }),
});
